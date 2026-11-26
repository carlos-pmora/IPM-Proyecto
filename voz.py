"""
voz.py - Lee las órdenes en voz alta con la voz del propio sistema operativo.

No necesita instalar nada:
  - macOS  : comando `say` (usa una voz en español si hay alguna instalada)
  - Windows: voz de Windows (System.Speech) a través de PowerShell, que se arranca
             una sola vez al principio para que la voz no llegue con retraso
  - Linux  : espeak-ng / espeak, si está instalado

Si no hay voz disponible, el juego funciona igual, pero en silencio.
"""
import base64
import re
import shutil
import subprocess
import sys

# Script de PowerShell: lee frases por la entrada estándar (UTF-8) y las dice.
_PS_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es*' } | Select-Object -First 1
if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }
$r = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), [System.Text.Encoding]::UTF8)
while (($l = $r.ReadLine()) -ne $null) {
    $s.SpeakAsyncCancelAll()
    if ($l.Length -gt 0) { [void]$s.SpeakAsync($l) }
}
"""


class Voz:
    def __init__(self, activa=True):
        self.activa = activa
        self.disponible = False
        self._proc = None        # proceso de la frase actual (Mac / Linux)
        self._ps = None          # PowerShell permanente (Windows)
        self._cmd = None
        try:
            if sys.platform == "darwin" and shutil.which("say"):
                voz = self._voz_mac()
                self._cmd = ["say"] + (["-v", voz] if voz else [])
                self.disponible = True
            elif sys.platform.startswith("win"):
                self._iniciar_windows()
            else:
                espeak = shutil.which("espeak-ng") or shutil.which("espeak")
                if espeak:
                    self._cmd = [espeak, "-v", "es"]
                    self.disponible = True
        except Exception as e:  # la voz es un extra: si falla, se sigue sin ella
            print(f"[voz] No se puede usar la voz ({e}).")
            self.disponible = False

    @staticmethod
    def _voz_mac():
        """Busca una voz en español (primero de España) entre las instaladas."""
        try:
            salida = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        voces = re.findall(r"^(.+?)\s+(es_[A-Z]{2})\s+#", salida, re.MULTILINE)
        voces.sort(key=lambda v: v[1] != "es_ES")
        return voces[0][0].strip() if voces else None

    def _iniciar_windows(self):
        script = base64.b64encode(_PS_SCRIPT.encode("utf-16-le")).decode("ascii")
        self._ps = subprocess.Popen(
            ["powershell", "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass", "-EncodedCommand", script],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.disponible = True

    def decir(self, texto):
        """Dice la frase sin bloquear el juego (corta la anterior si sigue hablando)."""
        if not (self.activa and self.disponible):
            return
        try:
            if self._ps is not None:
                self._ps.stdin.write((texto.replace("\n", " ") + "\n").encode("utf-8"))
                self._ps.stdin.flush()
            else:
                self.callar()
                self._proc = subprocess.Popen(self._cmd + [texto], stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL)
        except (OSError, ValueError):
            self.disponible = False

    def callar(self):
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        if self._ps is not None and self.disponible:
            try:
                self._ps.stdin.write(b"\n")  # línea vacía = cortar lo que esté diciendo
                self._ps.stdin.flush()
            except (OSError, ValueError):
                pass

    def cerrar(self):
        self.callar()
        if self._ps is not None:
            try:
                self._ps.stdin.close()
                self._ps.wait(timeout=2)
            except (OSError, ValueError, subprocess.SubprocessError):
                self._ps.kill()
            self._ps = None


if __name__ == "__main__":
    # Prueba rápida: python voz.py
    import time
    v = Voz()
    print("Voz disponible:", v.disponible, v._cmd or "(PowerShell)" if v.disponible else "")
    v.decir("Simón dice: levanta el brazo izquierdo")
    time.sleep(4)
    v.cerrar()
