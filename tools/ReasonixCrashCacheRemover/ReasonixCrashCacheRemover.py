import os
import shutil
import subprocess
import time

RECOVERY_CACHE = os.path.expandvars(
    r"C:\Users\Athos\AppData\Roaming\reasonix\sessions-v4\.recovery-cache"
)
IDADE_MINIMA_SEGUNDOS = 24 * 3600  # 24h

def reasonix_rodando():
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Reasonix.exe"],
            text=True, encoding="utf-8", errors="ignore"
        )
        return "Reasonix.exe" in out
    except Exception:
        return False

def idade(caminho):
    return time.time() - os.path.getmtime(caminho)

def limpar_cache():
    if not os.path.isdir(RECOVERY_CACHE):
        print(f"[skip] Não encontrado: {RECOVERY_CACHE}")
        return

    ativo = reasonix_rodando()
    modo = "CONSERVADOR (Reasonix aberto)" if ativo else "COMPLETO (Reasonix fechado)"
    print(f"[modo] {modo}\n")

    removidos = 0
    liberado = 0

    for entry in os.listdir(RECOVERY_CACHE):
        caminho = os.path.join(RECOVERY_CACHE, entry)
        if not os.path.isdir(caminho):
            continue

        if ativo and idade(caminho) < IDADE_MINIMA_SEGUNDOS:
            print(f"[pula] {entry}  (recente, Reasonix ativo)")
            continue

        try:
            tamanho = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(caminho)
                for f in fs
            )
        except Exception:
            tamanho = 0

        shutil.rmtree(caminho, ignore_errors=True)
        removidos += 1
        liberado += tamanho
        print(f"[rm] {entry}  ({tamanho / 1024 / 1024:.1f} MB)")

    print(f"\n{removidos} pastas removidas, {liberado / 1024 / 1024:.1f} MB liberados.")

if __name__ == "__main__":
    limpar_cache()