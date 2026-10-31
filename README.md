# ElegeCIPA

Sistema web whitelabel para condução de eleições de CIPA (Comissão Interna de Prevenção de Acidentes): cadastro de eleições e candidatos, votação sigilosa por matrícula e CPF, protocolo de comprovação, apuração e extrato em PDF.

## Funcionalidades

- **Eleitor:** login com matrícula + CPF (armazenados apenas como hash HMAC-SHA256), voto em candidato ou em branco, comprovante com protocolo.
- **Administrador (superusuário):** criação, edição e encerramento de eleições, CRUD de candidatos com foto, apuração (titulares, suplentes e não eleitos) e extrato em PDF.
- **Regras de integridade:** um voto por eleitor por eleição (constraint no banco), uma única eleição vigente, candidatos com votos não podem ser removidos, votos são somente leitura no admin do Django.

## Stack

Python 3.12+, Django 5.2, PostgreSQL (SQLite para desenvolvimento/testes), WhiteNoise, Gunicorn, ReportLab, pandas. Front-end com Tailwind via CDN e Font Awesome.

## Instalação

Os comandos abaixo são para o **PowerShell** (Windows). No Prompt de Comando (cmd), troque a ativação por `.venv\Scripts\activate.bat` e `Copy-Item` por `copy`.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Se o PowerShell bloquear a ativação do ambiente virtual, libere scripts para o seu usuário uma única vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Edite o `.env` (por exemplo, com `notepad .env`). `SECRET_KEY` e `MATRICULA_HASH_KEY` são obrigatórias fora de `DEBUG`; gere valores com:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> **Atenção:** `MATRICULA_HASH_KEY` não pode mudar depois que os eleitores forem importados, pois invalidaria todos os hashes.

Aplique as migrações e crie o administrador:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Para desenvolvimento local sem PostgreSQL, use no `.env`: `DEBUG=True` e `DB_ENGINE=django.db.backends.sqlite3`.

## Importação de eleitores

Prepare um CSV ou Excel com as colunas `matricula` e `CPF`:

```powershell
python manage.py import_matriculas eleitores.xlsx --mat-col matricula --cpf-col CPF
```

Opções: `--sheet` (nome ou índice da planilha). CPFs com zeros à esquerda perdidos são recuperados. Reexecutar a importação não duplica eleitores.

## Configuração

| Variável | Descrição | Padrão |
| --- | --- | --- |
| `SECRET_KEY` | Chave secreta do Django | obrigatória |
| `MATRICULA_HASH_KEY` | Chave do HMAC de matrícula/CPF | obrigatória |
| `DEBUG` | Modo de desenvolvimento | `False` |
| `ALLOWED_HOSTS` | Hosts separados por vírgula | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Origens com esquema, ex.: `https://votacao.exemplo.com` | vazio |
| `USE_HTTPS` | Ativa redirect HTTPS, cookies seguros e HSTS | `False` |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Banco de dados | PostgreSQL local |
| `SITE_NAME` | Nome exibido em títulos e na marca | `ElegeCIPA` |
| `ORGANIZATION_NAME` | Organização exibida no rodapé e no PDF | `Sua Organização` |
| `VAGAS_TITULARES`, `VAGAS_SUPLENTES` | Vagas na apuração | `6` e `4` |

## Personalização (whitelabel)

- **Logo e ícone:** substitua `ElegeCIPA/eleicao/static/eleicao/img/logo.svg`, `favicon.svg` e `avatar-placeholder.svg`.
- **Cores:** `primary` e `accent` na configuração do Tailwind em `ElegeCIPA/eleicao/templates/base.html`.
- **Unidades:** lista `UNIDADES` em `ElegeCIPA/eleicao/models.py` (gere uma migração após alterar).

## Testes

No PowerShell, defina as variáveis na sessão atual e execute:

```powershell
$env:DEBUG = "True"
$env:DB_ENGINE = "django.db.backends.sqlite3"
python manage.py test
```

No Prompt de Comando (cmd), use `set DEBUG=True` e `set DB_ENGINE=django.db.backends.sqlite3`.

## Deploy

```powershell
python manage.py collectstatic --noinput
```

O Gunicorn (usado no `Procfile`) só roda em Linux/macOS. Em um servidor Windows, use o Waitress:

```powershell
pip install waitress
waitress-serve --port=8000 ElegeCIPA.wsgi:application
```

- Defina `DEBUG=False`, `USE_HTTPS=True` e `CSRF_TRUSTED_ORIGINS` atrás de um proxy que envie `X-Forwarded-Proto`.
- Arquivos estáticos são servidos pelo WhiteNoise. **Fotos de candidatos (`/media/`) só são servidas pelo Django em modo `DEBUG`**; em produção, sirva o diretório `media/` pelo servidor web (Nginx, por exemplo) ou use armazenamento de objetos.
- O limitador de tentativas de login usa o cache padrão (memória por processo). Com vários workers, configure um cache compartilhado (Redis/Memcached) para um bloqueio efetivo.

## Estrutura

```
ElegeCIPA/
├── settings.py, urls.py, wsgi.py, asgi.py
└── eleicao/
    ├── models.py, forms.py, views.py, urls.py, admin.py
    ├── pdf.py, utils.py, context_processors.py
    ├── management/commands/import_matriculas.py
    ├── migrations/
    ├── static/eleicao/        css, js e imagens
    └── templates/
```

## Observação sobre sigilo do voto

O modelo `Voto` associa eleitor, candidato e protocolo para permitir comprovação e impedir voto duplo. Isso significa que quem tem acesso direto ao banco de dados pode relacionar votos a eleitores (identificados apenas por hash). Restrinja o acesso ao banco e ao admin do Django.
