import sys, asyncio, time
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')
from app.services.llm_router_service import LLMRouterService, LLMRequest

async def main():
    r = LLMRouterService()
    for nom in ("gpu_gemma", "gpu_qwen"):
        p = r.providers.get(nom)
        if not p:
            print(f"  {nom} : absent"); continue
        mod = list(p.get("models", {}).keys())
        print(f"  {nom:<10} modeles : {mod}")
        try:
            t = time.time()
            req = LLMRequest(
                prompt="Reponds uniquement par ce JSON, sans aucune explication : {\"test\":\"ok\"}",
                agent_type="raj", max_tokens=400, temperature=0.1)
            res = await r.complete(LLMRequest(prompt=req.prompt, agent_type="raj", max_tokens=400, temperature=0.1, force_provider=f"{nom}/{mod[0]}"))
            c = (getattr(res, "content", "") or "")[:60]
            print(f"             -> {int((time.time()-t)*1000)} ms · {c!r}")
        except Exception as e:
            print(f"             -> ECHEC : {str(e)[:90]}")

asyncio.run(main())
