# lambda-auth

Serviço de autenticação de clientes por CPF, preparado para AWS Lambda. O endpoint `POST /auth/customer/token` valida o CPF, verifica se o cliente está ativo e emite um JWT.

## Arquitetura

- `src/lambda_auth/handler.py` é o entrypoint da Lambda e compõe os componentes.
- `adapters/api_gateway.py` converte eventos HTTP v1/v2 do API Gateway para o contrato interno.
- `application/ports/application.py` define a porta chamada pelo adaptador.
- `application/health.py` contém o caso de uso de saúde.
- `application/authentication.py` valida o CPF, consulta a porta de clientes ativos e monta as claims permitidas.
- `adapters/postgres_customer_repository.py` consulta apenas o ID de clientes ativos na tabela compartilhada.
- `adapters/kms_token_signer.py` prepara a assinatura RS256 e o JWKS via KMS.

O handler não registra nem devolve o evento recebido. O exemplo local contém somente uma chamada GET para `/health`.

## Requisitos e instalação

Use Python 3.12. Crie e ative um ambiente virtual e instale as ferramentas de desenvolvimento:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Em Linux ou macOS:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Configuração local

`.env.example` lista as variáveis sem credenciais ou segredos. O processo lê variáveis diretamente do ambiente; o arquivo não é carregado automaticamente. Em desenvolvimento local, use `DATABASE_URL` no ambiente. Na Lambda, informe `DATABASE_SECRET_ARN`; o handler busca a URL no Secrets Manager e mantém um cache em memória por cinco minutos. A Function precisa de `JWT_KMS_KEY_ID`, `JWT_KID`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_TTL_SECONDS` e `AWS_REGION` para emitir tokens. O emissor e a audiência do exemplo são placeholders e devem ser alinhados com o grupo. A assinatura via KMS segue a proposta do ADR e ainda precisa ser conciliada com a nota técnica da issue #64 sobre secret externo.

```powershell
$env:LOG_LEVEL = "INFO"
```

`LOG_LEVEL` aceita `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`; o padrão é `WARNING`.

O TTL aceita valores entre 1 e 900 segundos e usa 900 por padrão. O endpoint de autenticação retorna `503` quando a configuração necessária está ausente.

## Exercitar o handler localmente

No PowerShell:

```powershell
Get-Content .\examples\events\health-v2.json | python -m lambda_auth.local
```

Em Linux ou macOS:

```bash
python -m lambda_auth.local < examples/events/health-v2.json
```

O comando imprime a resposta no formato do API Gateway para a verificação de saúde. O fluxo de autenticação e o endpoint JWKS usam PostgreSQL e AWS KMS quando configurados; os testes usam fakes e não fazem chamadas AWS.

O handler expõe `POST /auth/customer/token` com corpo JSON `{ "cpf": "..." }` e `GET /.well-known/jwks.json`. CPF inválido retorna `422`; cliente inexistente ou inativo retorna a mesma resposta `401`; falhas de dependência retornam `503` sem detalhes internos.

## Verificações

```shell
python -m ruff format --check .
python -m ruff check .
python -m pytest --cov=lambda_auth --cov-report=term-missing --cov-fail-under=80
```

A mesma sequência roda na CI para pushes e pull requests. A CI só tem permissão de leitura do conteúdo do repositório e não acessa a AWS.
