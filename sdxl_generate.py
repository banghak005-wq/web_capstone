#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SDXL 1.0 generator (for RTX 3060 Ti 8GB)
 - LoRA 지원 (peft 필요)
 - VRAM 절약 옵션:
    * --cpu_vae            : VAE만 CPU(fp32)로 이동(+decode 입력 캐스팅)
    * --sequential_offload : 모듈별 순차 오프로딩
    * --cpu_offload        : 전체 모델 CPU 오프로딩(가장 느림)
 - 추가 절약: --xformers, --attention_slicing, --vae_slicing, --vae_tiling
 - 후처리 보정: --enhance (--enhance_preset low/medium/high)
 - 편의: --snap64 (가로/세로 64 배수 자동 스냅)
"""
#이쪽 코드는 그림 그리는 일만 수행합니다. 혼동하지 않도록 메모
import argparse
import importlib
import gc
import torch
from PIL import Image
from diffusers import StableDiffusionXLPipeline, EulerAncestralDiscreteScheduler
from diffusers.models.attention_processor import AttnProcessor
from torchvision import transforms as T
import torch.nn.functional as F

from io import BytesIO #이미지를 Webp 형태로 압축하여 최적화 하여 보낼 계획
# 이 아래는 server.py와 통신 용
from fastapi import FastAPI, Response
from pydantic import BaseModel
from io import BytesIO

app = FastAPI()

class GenReq(BaseModel):
    prompt: str

@app.post("/generate")
def generate(req: GenReq):
    img_bytes = get_image(req.prompt)
    return Response(content=img_bytes, media_type="image/webp")

_PIPELINE = None #파이프라인
_PIPELINE_DEVICE = None

# ------------------------------
# 간단 보정(언샤프+대비/감마)
# ------------------------------
to_tensor = T.ToTensor()
to_pil = T.ToPILImage()

def apply_enhance(pil_img: Image.Image, preset: str = "medium") -> Image.Image:
    x = to_tensor(pil_img).unsqueeze(0)
    if preset == "low":
        sharp_w, blur_w, contrast, gamma = 1.15, 0.15, 1.03, 1.00
    elif preset == "high":
        sharp_w, blur_w, contrast, gamma = 1.40, 0.40, 1.10, 0.98
    else:
        sharp_w, blur_w, contrast, gamma = 1.30, 0.30, 1.06, 0.99

    blur = F.avg_pool2d(x, kernel_size=3, stride=1, padding=1)
    sharp = torch.clamp(x * sharp_w - blur * blur_w, 0.0, 1.0)
    y = (sharp - 0.5) * contrast + 0.5
    y = torch.clamp(y, 0.0, 1.0)
    if gamma != 1.0:
        y = torch.clamp(y, 1e-6, 1.0) ** gamma
    return to_pil(y.squeeze(0))


# ------------------------------
# 인자
# ------------------------------
def parse_args():
    p = argparse.ArgumentParser("SDXL generator with LoRA + optional enhancement")
    p.add_argument("--prompt", required=True)
    p.add_argument("--neg", default="")
    p.add_argument("--lora", default=None)
    p.add_argument("--lora_scale", type=float, default=0.8)
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--cfg", type=float, default=6.5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--w", type=int, default=1024)
    p.add_argument("--h", type=int, default=1024)
    p.add_argument("--snap64", action="store_true")
    p.add_argument("--out", default="out_sdxl.png")
    p.add_argument("--safety", action="store_true")
    p.add_argument("--model", default="stabilityai/stable-diffusion-xl-base-1.0")
    p.add_argument("--scheduler", default="euler_a", choices=["euler_a"])
    p.add_argument("--xformers", action="store_true")
    p.add_argument("--attention_slicing", action="store_true")
    p.add_argument("--vae_slicing", action="store_true")
    p.add_argument("--vae_tiling", action="store_true")
    p.add_argument("--cpu_offload", action="store_true")
    p.add_argument("--sequential_offload", action="store_true")
    p.add_argument("--cpu_vae", action="store_true")
    p.add_argument("--enhance", action="store_true")
    p.add_argument("--enhance_preset", default="medium", choices=["low", "medium", "high"])
    return p.parse_args()


# ------------------------------
# 디바이스/해상도
# ------------------------------
def pick_device_and_dtype():
    if torch.cuda.is_available():
        return "cuda", torch.float16
    return "cpu", torch.float32

def snap_to_64(x: int) -> int:
    r = round(x / 64) * 64
    return max(64, r)


# ------------------------------
# 파이프라인
# ------------------------------
def build_pipeline(a, device, dtype): #테스트용으로 사용했던 함수이고 매번 파이프라인을 다시 만들기 때문에 운영할때는 쓰지 말 것
    pipe = StableDiffusionXLPipeline.from_pretrained(
        a.model,
        torch_dtype=dtype,
        use_safetensors=True,
        add_watermarker=False,
    )

    if not a.safety and hasattr(pipe, "safety_checker"):
        pipe.safety_checker = None

    if a.scheduler == "euler_a":
        pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)

    if a.xformers:
        try:
            pipe.enable_xformers_memory_efficient_attention()
            print(">> xFormers enabled")
        except Exception as e:
            print(">> xFormers not enabled:", e)

    if a.attention_slicing:
        pipe.enable_attention_slicing()
    if a.vae_slicing:
        pipe.enable_vae_slicing()
    if a.vae_tiling:
        pipe.enable_vae_tiling()

    if device == "cuda":
        if a.cpu_offload:
            pipe.enable_model_cpu_offload()
            print(">> CPU offload: STRONG")
        elif a.sequential_offload:
            pipe.enable_sequential_cpu_offload()
            print(">> CPU offload: MEDIUM")
        else:
            pipe.to(device)
            if a.cpu_vae:
                pipe.vae.to(device="cpu", dtype=torch.float32)
                # xFormers 비활성화 (CPU에선 기본 어텐션)
                try:
                    pipe.vae.set_attn_processor(AttnProcessor())
                except Exception:
                    pass
                # decode 입력을 VAE 쪽 dtype/device로 강제 캐스팅
                _orig_decode = pipe.vae.decode
                def _decode_cast_fp32(z, *args, **kwargs):
                    vae_device = next(pipe.vae.parameters()).device
                    if z.device != vae_device or z.dtype != torch.float32:
                        z = z.to(device=vae_device, dtype=torch.float32)
                    return _orig_decode(z, *args, **kwargs)
                pipe.vae.decode = _decode_cast_fp32
                if not a.vae_tiling:
                    pipe.enable_vae_tiling()
                print(">> CPU offload: LIGHT (VAE on CPU)")
    else:
        pipe.to(device)

    if a.lora:
        try:
            pipe.load_lora_weights(a.lora, adapter_name="lora")
            pipe.set_adapters(["lora"], adapter_weights=[a.lora_scale])
            print(f">> LoRA loaded: {a.lora} (scale={a.lora_scale})")
        except Exception as e:
            print(">> LoRA load failed:", e)

    return pipe

def get_pipeline(): #파이프라인 재사용
    global _PIPELINE, _PIPELINE_DEVICE

    if _PIPELINE is not None:
        return _PIPELINE

    device, dtype = pick_device_and_dtype()
    print(f">> initializing pipeline on {device} ({dtype})")

    # argparse a 없이 쓰기 위해 build_pipeline 약간 수정
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=dtype,
        use_safetensors=True,
        add_watermarker=False,
    )

    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
        pipe.scheduler.config
    )

    if device == "cuda":
        pipe.to(device)
        try:
            pipe.enable_xformers_memory_efficient_attention()
        except Exception:
            pass
        pipe.enable_vae_tiling()
    else:
        pipe.to("cpu")

    _PIPELINE = pipe
    _PIPELINE_DEVICE = device
    return _PIPELINE


# ------------------------------
# VRAM 완전 플러시 유틸
# ------------------------------
def flush_vram_and_context():
    # cuBLASLt / xformers workspace 정리(우회 임포트로 torch 재바인딩 방지)
    try:
        _torch_c = importlib.import_module("torch._C")
        _torch_c._cuda_clearCublasLtWorkspace()
    except Exception:
        pass
    gc.collect()
    torch.cuda.ipc_collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


# ------------------------------
# 메인
# ------------------------------
def generate_image(
    prompt: str,
    negative_prompt: str = "",
    *,
    width: int = 768,
    height: int = 768,
    steps: int = 30,
    cfg: float = 6.5,
    seed: int | None = None,

    # ===== 출력 형태 =====
    output: str = "pil",          # "pil" | "tensor" | "png"

    # ===== CPU/VRAM 조절 =====
    cpu_vae: bool = False,        # VAE만 CPU(fp32) (VRAM↓, CPU↑, 느림↑)
    offload: str = "none",        # "none" | "sequential" | "full" (VRAM↓, CPU↑, 느림↑)
    xformers: bool = True,
    vae_tiling: bool = True,

    # ===== LoRA =====
    lora_path: str | None = None,
    lora_scale: float = 0.8,

    # (선택) GPU 후처리
    enhance: bool = True,
    enhance_preset: str = "medium",   # "low"|"medium"|"high"
):
    if output not in ("pil", "tensor", "png"):
        raise ValueError("output must be one of: 'pil', 'tensor', 'png'")
    if offload not in ("none", "sequential", "full"):
        raise ValueError("offload must be one of: 'none', 'sequential', 'full'")

    # 설정별 파이프라인 캐시 (generate_image만 바꿔도 globals로 가능)
    cache = globals().setdefault("_PIPELINE_CACHE", {})
    meta = globals().setdefault("_PIPELINE_META", {})  # key -> {"lora_path":..., "lora_scale":...}

    device, dtype = pick_device_and_dtype()
    key = (device, str(dtype), cpu_vae, offload, xformers, vae_tiling)

    pipe = cache.get(key)
    if pipe is None:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=dtype,
            use_safetensors=True,
            add_watermarker=False,
        )
        pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)

        # 안전체크는 필요 없으면 끄는 게 보통 VRAM/속도에 이득
        if hasattr(pipe, "safety_checker"):
            pipe.safety_checker = None

        if device == "cuda":
            if offload == "full":
                pipe.enable_model_cpu_offload()
            elif offload == "sequential":
                pipe.enable_sequential_cpu_offload()
            else:
                pipe.to("cuda")

            if xformers:
                try:
                    pipe.enable_xformers_memory_efficient_attention()
                except Exception:
                    pass

            if vae_tiling:
                pipe.enable_vae_tiling()

            if cpu_vae:
                pipe.vae.to(device="cpu", dtype=torch.float32)
                try:
                    pipe.vae.set_attn_processor(AttnProcessor())
                except Exception:
                    pass

                _orig_decode = pipe.vae.decode
                def _decode_cast_fp32(z, *args, **kwargs):
                    vae_device = next(pipe.vae.parameters()).device
                    if z.device != vae_device or z.dtype != torch.float32:
                        z = z.to(device=vae_device, dtype=torch.float32)
                    return _orig_decode(z, *args, **kwargs)
                pipe.vae.decode = _decode_cast_fp32
        else:
            pipe.to("cpu")

        cache[key] = pipe
        meta[key] = {"lora_path": None, "lora_scale": None}

    # ===== LoRA 적용(파이프라인 재사용을 위해 "변경 시에만" 로드/갱신) =====
    current = meta.get(key, {"lora_path": None, "lora_scale": None})
    cur_path = current.get("lora_path")
    cur_scale = current.get("lora_scale")

    # 1) LoRA 꺼야 하는데 켜져있던 상태면: adapters 비활성화
    if lora_path is None and cur_path is not None:
        try:
            pipe.set_adapters([], adapter_weights=[])
        except Exception:
            # set_adapters가 없는 버전이면 fallback: scale 0 느낌으로
            try:
                pipe.set_adapters(["lora"], adapter_weights=[0.0])
            except Exception:
                pass
        meta[key] = {"lora_path": None, "lora_scale": None}

    # 2) LoRA 켜야 하면: (경로 바뀌면 로드, 스케일만 바뀌면 가중치만 갱신)
    if lora_path is not None:
        if cur_path != lora_path:
            # 다른 LoRA로 교체
            try:
                # 가능하면 이전 adapter들 정리
                try:
                    pipe.set_adapters([], adapter_weights=[])
                except Exception:
                    pass

                pipe.load_lora_weights(lora_path, adapter_name="lora")
                pipe.set_adapters(["lora"], adapter_weights=[float(lora_scale)])
            except Exception as e:
                raise RuntimeError(f"LoRA load/apply failed: {e}")
            meta[key] = {"lora_path": lora_path, "lora_scale": float(lora_scale)}
        else:
            # 같은 LoRA인데 scale만 변경
            if cur_scale != float(lora_scale):
                try:
                    pipe.set_adapters(["lora"], adapter_weights=[float(lora_scale)])
                except Exception:
                    pass
                meta[key] = {"lora_path": lora_path, "lora_scale": float(lora_scale)}

    # ===== 시드 =====
    gen = torch.Generator(device=pipe.device)
    if seed is not None:
        gen = gen.manual_seed(seed)

    # ===== 생성 =====
    with torch.inference_mode():
        out = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=cfg,
            generator=gen,
            output_type="latent" if output in ("tensor", "png") else "pil",
        )

    if output == "pil":
        img = out.images[0].convert("RGB").copy()
        del out
        if device == "cuda":
            torch.cuda.empty_cache()
        return img

    # latent 경로: 가능한 한 GPU 유지
    latents = out.latents if hasattr(out, "latents") else out.images
    del out

    latents = latents / pipe.vae.config.scaling_factor
    img = pipe.vae.decode(latents).sample
    img = (img / 2 + 0.5).clamp(0, 1)  # (1,3,H,W)

    # ===== (선택) GPU 후처리 =====
    if enhance:
        if enhance_preset == "low":
            sharp_w, blur_w, contrast, gamma = 1.15, 0.15, 1.03, 1.00
        elif enhance_preset == "high":
            sharp_w, blur_w, contrast, gamma = 1.40, 0.40, 1.10, 0.98
        else:
            sharp_w, blur_w, contrast, gamma = 1.30, 0.30, 1.06, 0.99

        blur = F.avg_pool2d(img, kernel_size=3, stride=1, padding=1)
        sharp = (img * sharp_w - blur * blur_w).clamp(0, 1)
        y = ((sharp - 0.5) * contrast + 0.5).clamp(0, 1)
        if gamma != 1.0:
            y = y.clamp(1e-6, 1.0) ** gamma
        img = y

    if output == "tensor":
        return img

    # output == "png" : PNG 인코딩은 CPU 1회 필수
    import io
    img_u8 = (img[0].permute(1, 2, 0) * 255).to(torch.uint8).cpu().numpy()
    pil = Image.fromarray(img_u8, mode="RGB")
    buf = io.BytesIO()
    pil.save(buf, format="PNG", compress_level=6)
    if device == "cuda":
        torch.cuda.empty_cache()
    return buf.getvalue()
#api 용 함수
from fastapi import FastAPI, Response, Request
from pydantic import BaseModel
from io import BytesIO
from fastapi import HTTPException
import requests
app = FastAPI()
class DrawReq(BaseModel):
    prompt: str

def get_image(prompt):
    #img = generate_image("man", output="tensor", offload="none", cpu_vae=False) cpu 왕복 최소화
    #img = generate_image("man", output="pil", offload="full", cpu_vae=True) cpu 사용 극대화
    
    image = generate_image(prompt)  # PIL.Image, 768x768 PNG

    if image.mode != "RGB": #RGB 아니면 RGB로 변환
        image = image.convert("RGB")

    buf = BytesIO()
    image.save(buf, format="WEBP", quality=80, method=6)
    buf.seek(0)

    img_bytes = buf.getvalue()
    return img_bytes

@app.post("/get_image")
def draw(req: DrawReq):
    img_bytes = get_image(req.prompt)
    return Response(content=img_bytes, media_type="image/webp")


def main():
    pass
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7300)

