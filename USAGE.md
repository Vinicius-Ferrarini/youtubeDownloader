# USAGE — Baixador de Áudio/Vídeo do YouTube

Projeto local para baixar **MP3 (áudio)** ou **MP4 (vídeo até 1080p)** do YouTube,
para uso pessoal/familiar. Roda 100% na sua máquina, só em `localhost`.

---

## 1. Pré-requisitos

- **Python 3.10 ou superior** (`python --version`)
- **ffmpeg** instalado no sistema e acessível no `PATH`
  - Verifique com: `ffmpeg -version`
  - Windows (uma das opções):
    - `winget install Gyan.FFmpeg` — depois **feche e reabra o terminal**
    - ou `choco install ffmpeg`
    - ou baixe em <https://www.gyan.dev/ffmpeg/builds/> e adicione a pasta `bin` ao `PATH`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg` (ou equivalente da sua distro)

> O `ffmpeg` **não** vem no `requirements.txt` de propósito: é um binário externo,
> não um pacote Python.

---

## 2. Ambiente virtual e dependências

Na pasta do projeto:

### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Rodar o servidor

```bash
uvicorn main:app --reload
```

O `--reload` reinicia o servidor sozinho quando você edita o código
(útil durante ajustes; pode omitir para uso normal).

---

## 4. Acessar

Abra no navegador:

```
http://localhost:8000
```

---

## 5. Passo a passo de teste manual

1. Com o servidor rodando, abra <http://localhost:8000>.
2. Cole um link de um vídeo **curto** (ex.: algo de 1–3 minutos). Funcionam
   links normais, `youtu.be/...` e `youtube.com/shorts/...`.
3. Clique em **Verificar**. Deve aparecer:
   - a **capa** (thumbnail) do vídeo
   - **título**, **canal**, **duração**
   - o **tamanho estimado** do arquivo
4. Em **Formato**, escolha **MP3 (áudio)** e deixe a qualidade em **Alta (320 kbps)**.
5. Clique em **Baixar**. Um cronômetro/spinner aparece enquanto o servidor
   baixa e converte.
6. Ao terminar:
   - o navegador dispara o **download do arquivo** automaticamente;
   - uma cópia também fica salva em **`./downloads/`** dentro da pasta do projeto.
7. Abra o `.mp3` baixado em qualquer player e confirme que **toca do início ao
   fim com o áudio correto**.
8. (Opcional) Repita escolhendo **MP4 (vídeo)** e confirme que o vídeo abre com
   imagem + som.

### Se der erro

As mensagens de erro aparecem **na própria tela**, em português, para casos
comuns: vídeo indisponível, privado, com restrição de idade, bloqueado na
região, ou quando o YouTube exige login. Se a mensagem citar o `ffmpeg`,
volte ao passo 1 dos pré-requisitos.

---

## 6. Estrutura

```
youtubeDownloader/
├── main.py            # app FastAPI: serve o frontend e as rotas /info e /download
├── downloader.py      # lógica de yt-dlp + ffmpeg (metadados, download, conversão)
├── static/
│   └── index.html     # frontend de página única (HTML + JS puro)
├── downloads/         # arquivos baixados (fora do controle de versão)
├── requirements.txt
├── .gitignore
└── USAGE.md
```

### Endpoints (uso interno do frontend)

- `POST /info` — `{ "url": "..." }` → título, canal, duração, thumbnail e
  tamanho estimado. **Não baixa nada.**
- `POST /download` — `{ "url": "...", "format": "mp3"|"mp4", "quality": "high"|"medium" }`
  → baixa, converte se necessário, salva em `./downloads/` e devolve o arquivo
  diretamente para download.

---

## 7. Nota de uso

Isto é para **uso pessoal/familiar**: não redistribua publicamente o conteúdo
baixado e não exponha este servidor à internet por enquanto — ele foi feito
para rodar apenas em `localhost`, sem autenticação. Respeite os Termos de
Serviço do YouTube e os direitos dos autores.
