# Roteiro de testes manuais

Roteiro para validação funcional do ElegeCIPA antes de uma eleição real ou de uma nova versão. Complementa os testes automatizados (`python manage.py test`), que cobrem regras de negócio, mas não a experiência no navegador, a aparência nem a implantação.

## Como usar

1. Execute os casos na ordem: os últimos dependem dos dados criados pelos primeiros.
2. Marque o resultado de cada caso: `[x]` passou, `[ ]` não executado, `[F]` falhou.
3. Para cada falha, anote ID do caso, o que ocorreu e uma captura de tela.
4. Use um ambiente de teste com banco descartável. **Nunca** execute este roteiro em um banco com votos reais.

| Campo | Valor |
| --- | --- |
| Versão testada (commit) | |
| Data | |
| Responsável | |
| Navegador / versão | |
| Ambiente (dev, homologação) | |

## 0. Preparação

Os comandos são para o PowerShell. A instalação completa está no [README](../README.md).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

No `.env`, para teste local, use `DEBUG=True` e `DB_ENGINE=django.db.backends.sqlite3`. Depois:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py import_matriculas docs\eleitores_exemplo.csv
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

### Massa de dados

Arquivo `docs/eleitores_exemplo.csv`:

| Matrícula | CPF informado | Observação |
| --- | --- | --- |
| 1001 | 11111111111 | Eleitor comum |
| 1002 | 22222222222 | Eleitor comum |
| 1003 | 33333333333 | Eleitor comum |
| 1004 | 44444444444 | Eleitor comum |
| 1005 | 1234567890 | CPF sem o zero inicial; deve ser aceito como `01234567890` |
| 1006 | (vazio) | Eleitor sem CPF; não deve conseguir entrar |

Crie também um usuário comum (não superusuário) pelo admin do Django: `comum` / senha à sua escolha.

---

## 1. Importação de eleitores

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| IMP-01 | Execute `python manage.py import_matriculas docs\eleitores_exemplo.csv` | Mensagem `Importação concluída: 6 criados, 0 ignorados.` | [ ] |
| IMP-02 | Execute o mesmo comando novamente | `0 criados`; nenhum eleitor duplicado | [ ] |
| IMP-03 | Execute com `--mat-col inexistente` | Erro `Coluna 'inexistente' não encontrada no arquivo.` | [ ] |
| IMP-04 | Execute com um caminho de arquivo que não existe | Erro `Erro ao ler o arquivo` sem stack trace | [ ] |
| IMP-05 | Converta o CSV para `.xlsx` e importe | Importação funciona sem criar duplicados | [ ] |
| IMP-06 | Execute `python manage.py shell -c "from ElegeCIPA.eleicao.models import Eleitor; print(Eleitor.objects.values().first())"` | Apenas hashes de 64 caracteres; nenhuma matrícula ou CPF em texto puro | [ ] |

## 2. Acesso do eleitor

Pré-condição: não há eleição vigente. Abra uma janela anônima.

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| ACE-01 | Acesse `/` | Página inicial com título, texto de apresentação e botão **Votar**; sem logo ou nome de terceiros | [ ] |
| ACE-02 | Clique em **Votar** | Tela de login com abas **Eleitor** e **Administrador**; aba Eleitor ativa | [ ] |
| ACE-03 | Login com matrícula `1001` e CPF `11111111111` | Redireciona para a lista de candidatos; menu mostra **Sair** | [ ] |
| ACE-04 | Clique em **Sair** | Volta à página inicial; ao acessar `/candidatos/` é redirecionado ao login | [ ] |
| ACE-05 | Login com matrícula `1005` e CPF `01234567890` | Entra normalmente (zero inicial recuperado na importação) | [ ] |
| ACE-06 | Login com CPF errado | Mensagem `Matrícula ou CPF inválidos.`; permanece na tela de login | [ ] |
| ACE-07 | Login com matrícula inexistente | Mesma mensagem genérica (não revela qual campo está errado) | [ ] |
| ACE-08 | Digite letras no campo CPF e na matrícula | Campos aceitam apenas dígitos | [ ] |
| ACE-09 | Informe CPF com 10 dígitos | Mensagem `Digite apenas números, com 11 dígitos.` | [ ] |
| ACE-10 | Login com matrícula `1006` (sem CPF cadastrado) | Login recusado | [ ] |
| ACE-11 | Acesse `/candidatos/` sem estar logado | Redireciona para `/login/` | [ ] |
| ACE-12 | Logado como eleitor, acesse `/painel-admin/` | Redireciona para o login; painel não é exibido | [ ] |

## 3. Acesso do administrador

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| ADM-01 | Na aba **Administrador**, entre com o superusuário | Abre `/painel-admin/` | [ ] |
| ADM-02 | Entre com senha errada | `Usuário ou senha incorretos, ou sem permissão.` | [ ] |
| ADM-03 | Entre com o usuário comum `comum` (credenciais corretas) | Login recusado com a mesma mensagem | [ ] |
| ADM-04 | Acesse `/admin/` com o superusuário | Admin do Django abre; modelo **Eleitores** não aparece | [ ] |
| ADM-05 | No admin, abra um voto (após o cenário 6) | Campos somente leitura; botões de adicionar, salvar e excluir indisponíveis | [ ] |

## 4. Bloqueio por tentativas

Use uma janela anônima nova.

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| BLQ-01 | Erre o login 4 vezes e acerte na 5ª tentativa | Login funciona; contador é zerado | [ ] |
| BLQ-02 | Saia e erre o login 5 vezes seguidas | A 6ª tentativa mostra `Muitas tentativas inválidas. Aguarde alguns minutos e tente novamente.` | [ ] |
| BLQ-03 | Com o bloqueio ativo, tente entrar com credenciais corretas (eleitor e administrador) | Ambos continuam bloqueados | [ ] |
| BLQ-04 | Aguarde 15 minutos (ou reinicie o servidor em desenvolvimento) e tente de novo | Login volta a funcionar | [ ] |

## 5. Gestão de eleições (administrador)

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| ELE-01 | No painel, clique em **Criar Eleição** e informe início 10 dias atrás e fim daqui a 10 dias | Mensagem `Eleição criada com sucesso! ID: n`; painel mostra **Eleição atual** com as datas | [ ] |
| ELE-02 | Tente criar outra eleição com a primeira ainda vigente | Mensagem `Existe eleição em andamento. Encerre-a antes de criar uma nova.` | [ ] |
| ELE-03 | Edite a eleição colocando a data de fim anterior à de início | Formulário recusa com mensagem de erro; nada é salvo | [ ] |
| ELE-04 | Deixe as datas em branco e salve | Formulário indica campos obrigatórios | [ ] |
| ELE-05 | Clique no ícone de edição das datas e altere o fim | Mensagem `Eleição atualizada com sucesso!`; painel reflete a nova data | [ ] |
| ELE-06 | Em **Eleições Anteriores** | Lista somente eleições encerradas; vazia se for a primeira | [ ] |

## 6. Gestão de candidatos (administrador)

Pré-condição: eleição vigente (ELE-01).

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| CAN-01 | **Cadastrar Candidatos** com foto PNG pequena, nome, cargo, setor, unidade e eleição vigente | Mensagem `Candidato ... cadastrado com sucesso!`; aparece no painel com a foto | [ ] |
| CAN-02 | Cadastre mais 4 candidatos, um deles sem foto | Candidato sem foto exibe a imagem padrão (silhueta cinza) | [ ] |
| CAN-03 | Ao escolher o arquivo, o botão mostra o nome do arquivo selecionado | Nome exibido no lugar de `Selecionar arquivo` | [ ] |
| CAN-04 | Tente enviar uma imagem maior que 5 MB | Erro `A imagem deve ter no máximo 5 MB.` | [ ] |
| CAN-05 | Tente enviar um arquivo que não é imagem (ex.: `.txt` renomeado para `.png`) | Formulário recusa o arquivo | [ ] |
| CAN-06 | O seletor de eleição do cadastro | Lista somente a eleição vigente | [ ] |
| CAN-07 | Deixe nome e cargo em branco | Erros nos campos obrigatórios; nada é salvo | [ ] |
| CAN-08 | Edite um candidato (cargo) sem enviar nova foto | Alteração salva e foto anterior mantida | [ ] |
| CAN-09 | Exclua um candidato sem votos | Pede confirmação; ao confirmar, mensagem `Candidato removido com sucesso!` | [ ] |
| CAN-10 | Cancele a confirmação de exclusão | Candidato permanece | [ ] |
| CAN-11 | Digite o nome `<b>Teste</b>` em um candidato | Aparece literalmente como texto, sem negrito, em todas as telas | [ ] |

## 7. Votação

Pré-condição: eleição vigente com 5 candidatos e eleitores importados.

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| VOT-01 | Entre como `1001` | Lista de candidatos em ordem alfabética, com foto, cargo e setor, mais o cartão **Votar em Branco** | [ ] |
| VOT-02 | Clique em **Votar** em um candidato | Tela de confirmação com a foto e o nome; aviso de que não é possível alterar o voto | [ ] |
| VOT-03 | Clique em **Cancelar** | Volta à lista; nenhum voto registrado | [ ] |
| VOT-04 | Confirme o voto | Tela **Voto Registrado com Sucesso!** com candidato, protocolo (`CIPA` + ano + 6 caracteres), data/hora e cargo | [ ] |
| VOT-05 | Anote o protocolo e atualize a página (F5) | Comprovante continua exibido; nenhum voto duplicado | [ ] |
| VOT-06 | Use o botão Voltar do navegador até a confirmação e confirme de novo | Mensagem `Você já votou nesta eleição. Sua sessão foi encerrada.`; é levado à página inicial | [ ] |
| VOT-07 | Entre novamente como `1001` e tente votar | Voto recusado; continua com apenas 1 voto | [ ] |
| VOT-08 | Entre como `1002` e vote em **Voto em Branco** | Confirmação própria; comprovante exibe `VOTO EM BRANCO` e protocolo | [ ] |
| VOT-09 | Vote com `1003`, `1004` e `1005` em candidatos diferentes (distribua para gerar eleitos, suplentes e não eleitos) | Todos recebem protocolos diferentes | [ ] |
| VOT-10 | Como `1003`, abra manualmente `/protocolo-voto/<id>/` de outro eleitor | Página não encontrada (404) | [ ] |
| VOT-11 | Digite `/registrar-voto/<id>/` diretamente na barra de endereços (método GET) | `405 Method Not Allowed`; nenhum voto registrado | [ ] |
| VOT-12 | Com a eleição vigente encerrada (cenário 8), entre e abra a lista | Aviso `Não há eleição em andamento` | [ ] |

## 8. Encerramento e apuração

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| APU-01 | No painel, **Encerrar Eleição** e escolha a eleição | Tela de confirmação com o ID da eleição | [ ] |
| APU-02 | Confirme o encerramento | Mensagem `Eleição ID n encerrada com sucesso!` e abertura da apuração | [ ] |
| APU-03 | Confira a apuração | Seções **Candidatos Eleitos** (até 6), **Suplentes** (até 4) e **Não Eleitos**; cada cartão com a contagem de votos | [ ] |
| APU-04 | Confira o resumo | Total de votos, válidos, brancos, eleitos, suplentes e não eleitos; soma coerente com os votos feitos | [ ] |
| APU-05 | Candidato sem nenhum voto | Sempre em **Não Eleitos** | [ ] |
| APU-06 | Candidatos empatados | Desempate por ordem alfabética do nome | [ ] |
| APU-07 | Painel → **Apurar Votos** → escolha uma eleição | Abre a apuração da eleição escolhida | [ ] |
| APU-08 | Tente escolher sem selecionar eleição | Mensagem pedindo para selecionar uma eleição | [ ] |
| APU-09 | Tente excluir um candidato que recebeu votos (eleição anterior) | Mensagem `Candidatos que já receberam votos não podem ser removidos.` | [ ] |
| APU-10 | Edite um candidato com votos e tente trocá-lo de eleição | Erro `Candidato com votos não pode mudar de eleição.` | [ ] |
| APU-11 | **Eleições Anteriores** | A eleição encerrada aparece como encerrada | [ ] |
| APU-12 | Crie uma nova eleição após encerrar a anterior | Permitido; a anterior não volta a ficar vigente | [ ] |

## 9. Extrato em PDF

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| PDF-01 | Na apuração, **Gerar PDF da Apuração** | Abre PDF em nova aba; nome `Apuracao_CIPA_<início>_<fim>.pdf` | [ ] |
| PDF-02 | Confira o cabeçalho | Título com o período e o nome da organização configurado em `ORGANIZATION_NAME` | [ ] |
| PDF-03 | Confira a tabela | Uma linha por voto, em ordem cronológica, com número, data/hora, candidato (ou `Voto em Branco`) e protocolo | [ ] |
| PDF-04 | Compare os protocolos com os anotados em VOT-04 e VOT-08 | Os protocolos conferem | [ ] |
| PDF-05 | Confira o resumo no fim | Totais iguais aos da tela; participação = votos ÷ eleitores cadastrados | [ ] |
| PDF-06 | Gere o PDF com mais de 50 votos (use um script ou importe mais eleitores) | Tabela continua nas páginas seguintes sem sobrepor texto; resumo não é cortado | [ ] |
| PDF-07 | Acesse `/gerar-extrato-pdf/` como eleitor ou anônimo | Redireciona para o login; PDF não é entregue | [ ] |

## 10. Segurança

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| SEG-01 | Com o DevTools aberto, confira os cabeçalhos de qualquer página | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` | [ ] |
| SEG-02 | Em produção com HTTPS, confira cookies de sessão e CSRF | Marcados como `Secure` e `SameSite=Lax`; `Strict-Transport-Security` presente | [ ] |
| SEG-03 | Em produção, acesse via `http://` | Redireciona para `https://` | [ ] |
| SEG-04 | Remova `SECRET_KEY` do `.env` com `DEBUG=False` e inicie o sistema | Falha com erro de configuração claro, sem iniciar | [ ] |
| SEG-05 | Em produção, acesse uma URL inexistente com `DEBUG=False` | Página de erro genérica, sem detalhes técnicos | [ ] |
| SEG-06 | Deixe uma sessão de eleitor ociosa por mais de 2 horas | Sessão expira e exige novo login | [ ] |
| SEG-07 | Feche o navegador e reabra | Sessão não é mantida | [ ] |
| SEG-08 | No DevTools, remova o campo `csrfmiddlewaretoken` de um formulário e envie | `403 Forbidden` | [ ] |
| SEG-09 | Confira os arquivos do repositório | Nenhum `.env`, banco de dados, mídia ou segredo versionado | [ ] |
| SEG-10 | Tente acessar `/media/candidatos/` listando o diretório | Listagem de diretório não é exibida | [ ] |

## 11. Identidade visual (whitelabel)

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| WL-01 | Percorra todas as telas (inicial, login, candidatos, confirmação, comprovante, painel, apuração) | Nenhum logo, nome, cor ou texto de instituição específica | [ ] |
| WL-02 | Observe a aba do navegador | Favicon e título usam o nome configurado em `SITE_NAME` | [ ] |
| WL-03 | Altere `SITE_NAME` e `ORGANIZATION_NAME` no `.env` e reinicie | Títulos, rodapé e PDF refletem os novos valores | [ ] |
| WL-04 | Substitua `static/eleicao/img/logo.svg` por outro logotipo | Novo logo aparece no cabeçalho (após limpar o cache) | [ ] |
| WL-05 | Altere as cores `primary` e `accent` em `base.html` | Botões, abas e destaques mudam de cor em todas as telas | [ ] |
| WL-06 | Rodapé | Mostra o ano atual e a organização configurada | [ ] |

## 12. Layout e compatibilidade

Repita os casos ACE-03, VOT-02 a VOT-04 e APU-03 em cada combinação abaixo.

| ID | Ambiente | Resultado esperado | Status |
| --- | --- | --- | --- |
| LAY-01 | Chrome ou Edge, desktop (1920 px) | Layout íntegro, sem rolagem horizontal | [ ] |
| LAY-02 | Firefox, desktop | Idem | [ ] |
| LAY-03 | Safari (macOS ou iOS), se utilizado pelos eleitores | Idem | [ ] |
| LAY-04 | Celular Android, Chrome (360 px) | Menu hambúrguer funciona; botões tocáveis; sem texto cortado | [ ] |
| LAY-05 | iPhone, Safari | Idem | [ ] |
| LAY-06 | Tablet na vertical (768 px) | Cartões reorganizam em colunas sem sobreposição | [ ] |
| LAY-07 | Zoom de 200% | Conteúdo continua legível e utilizável | [ ] |
| LAY-08 | Navegação somente por teclado (Tab/Enter) no login e na votação | Todos os controles acessíveis, com foco visível | [ ] |
| LAY-09 | Rede lenta (3G simulado no DevTools) | Páginas carregam; estilos do Tailwind e ícones aparecem | [ ] |

## 13. Implantação (homologação ou produção)

| ID | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| IMPL-01 | `python manage.py collectstatic --noinput` | Concluído sem erros | [ ] |
| IMPL-02 | Inicie com o servidor de produção (Gunicorn no Linux; Waitress no Windows) e `DEBUG=False` | Sistema sobe e o CSS/JS carregam | [ ] |
| IMPL-03 | Cadastre candidato com foto e abra a lista de candidatos | A foto é exibida (o servidor web serve `/media/`) | [ ] |
| IMPL-04 | Banco PostgreSQL: `python manage.py migrate` em banco vazio e em banco com dados antigos | Migrações aplicam sem erro; unidades antigas convertidas para `UN1`–`UN7` | [ ] |
| IMPL-05 | Reinicie o servidor durante uma sessão de voto | Eleitor precisa entrar de novo; votos já registrados continuam | [ ] |
| IMPL-06 | Faça backup e restaure o banco em ambiente limpo | Dados e votos íntegros após a restauração | [ ] |
| IMPL-07 | Com 2 ou mais workers, repita BLQ-02 | Observe se o bloqueio é consistente; se não for, configure cache compartilhado (Redis/Memcached) | [ ] |
| IMPL-08 | Simule 20 a 50 eleitores votando ao mesmo tempo | Nenhum erro 500; nenhum voto duplicado por eleitor | [ ] |

---

## Registro de defeitos

| ID do caso | Descrição | Gravidade (alta/média/baixa) | Evidência | Situação |
| --- | --- | --- | --- | --- |
| | | | | |

## Critérios de aceite

- Todos os casos das seções 2 a 9 e 13 aprovados.
- Nenhum defeito de gravidade alta aberto.
- Nenhum caso das seções 10 e 11 reprovado.
- Testes automatizados (`python manage.py test`) sem falhas na mesma versão.
