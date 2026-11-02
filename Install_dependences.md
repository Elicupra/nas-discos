# Instalación de dependencias — disk-search (nas_discos.py)

Guía para Ubuntu (probado en Python 3.14, PEP 668).

## Por qué no `sudo pip install`

Ubuntu protege el Python del sistema (PEP 668). `sudo pip` ignora además el
entorno virtual activo. **Nunca uses `sudo pip install`**: instala siempre
dentro de un venv.

## 1. Crear el entorno virtual FUERA del repo

`python3 -m venv` falla en `~/red/repos/disk-search` con
`Error: [Errno 95] Operation not supported: 'lib' -> '.venv/lib64'` porque ese
filesystem no soporta symlinks (NTFS/exFAT/FUSE/red). El venv debe vivir en un
filesystem nativo (ext4):

```bash
# (opcional) confirma la causa
findmnt -T ~/red/repos/disk-search

# crea el venv en tu home
python3 -m venv ~/.venvs/disk-search
source ~/.venvs/disk-search/bin/activate

# verifica que pip apunta al venv (no a /usr/bin/pip)
which pip
# → /home/ubuntu/.venvs/disk-search/bin/pip
```

## 2. Dependencias Python

```bash
pip install requests beautifulsoup4 playwright
```

## 3. Navegador Chromium (necesario para PcComponentes y Amazon)

```bash
python -m playwright install chromium
```

Si Chromium no arranca por librerías del sistema (errores tipo
`libnss3.so: cannot open`):

```bash
sudo apt install -y libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 \
     libcups2t64 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
     libxrandr2 libgbm1 libasound2t64
# (nombres con t64 en Ubuntu 24.04+; sin el sufijo en versiones anteriores)
```

## 4. Verificación

```bash
python -c "import requests, bs4, playwright; print('deps OK')"

cd ~/red/repos/disk-search
python nas_discos.py --demo --once   # prueba la UI sin internet
python nas_discos.py --debug         # búsqueda real con log por página
```

## 5. Uso habitual

```bash
cd ~/red/repos/disk-search
source ~/.venvs/disk-search/bin/activate
python nas_discos.py              # servidor en http://localhost:8765
python nas_discos.py --headed     # si hay captcha, resuélvelo en la ventana
```

## Notas

- Si el captcha de Amazon bloquea la búsqueda, relanza con `--headed`.
- El estado de cada tienda (productos encontrados / errores) se muestra en la
  propia interfaz, bajo el resumen.
- `pipx` es una alternativa válida para herramientas sueltas, pero para este
  proyecto basta el venv.
