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

`.env.example` lista as variáveis sem credenciais ou segredos. O processo lê variáveis diretamente do ambiente; o arquivo não é carregado automaticamente. Em desenvolvimento local, use `DATABASE_URL` no ambiente. Na Lambda, informe `DATABASE_SECRET_ARN`; o handler busca a URL no Secrets Manager e mantém um cache em memória por cinco minutos. A Function precisa de `JWT_KMS_KEY_ID`, `JWT_KID`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_TTL_SECONDS` e `AWS_REGION` para emitir tokens RS256 com KMS. O emissor e a audiência do exemplo são placeholders e devem coincidir com a configuração do consumidor.

`JWT_ADDITIONAL_PUBLIC_KEYS_JSON` aceita uma lista JSON de objetos `{ "kid": "...", "kms_key_id": "..." }`. Essas chaves aparecem no JWKS para permitir rotação, mas nunca são usadas para assinar. O padrão `[]` mantém compatibilidade com a configuração de chave única. Identificadores vazios, campos extras e `kid` repetido — inclusive o `kid` ativo — fazem a inicialização falhar sem reproduzir o valor recebido.

```powershell
$env:LOG_LEVEL = "INFO"
```

`LOG_LEVEL` aceita `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`; o padrão é `WARNING`.

O TTL aceita valores entre 1 e 900 segundos e usa 900 por padrão. O endpoint de autenticação retorna `503` quando a configuração necessária está ausente.

## Rotação das chaves JWT

1. Configure a chave B em `JWT_ADDITIONAL_PUBLIC_KEYS_JSON`, mantendo A em `JWT_KID` e `JWT_KMS_KEY_ID`.
2. Implante e confirme que A e B aparecem em `GET /.well-known/jwks.json`; aguarde a propagação e os caches dos consumidores.
3. Torne B ativa e mantenha A como chave adicional. Somente B recebe permissão `kms:Sign`.
4. Registre o último instante possível de emissão por A. Remova A somente depois de TTL máximo, tolerância de relógio, cache JWKS e propagação acordados.
5. Durante a sobreposição, um rollback para A exige republicar A antes de voltar a assinar com ela.

O endpoint falha por inteiro com `503` se qualquer chave configurada não puder ser publicada. Isso evita entregar um JWKS parcial que invalidaria tokens ainda aceitos durante a transição.

## Preparação de infraestrutura

O módulo Terraform em [`infra/terraform`](infra/terraform/README.md) configura a Lambda, a role com permissões mínimas e a retenção de logs. Conta, região, segredo, chave KMS, rede e contrato JWT são entradas que precisam ser confirmadas com a equipe responsável antes de provisionar. O CI valida e empacota o serviço sem credenciais AWS; nenhuma função ou recurso AWS é criado por ele.

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
## Referências de arquitetura

As decisões que cruzam os quatro repositórios estão centralizadas na documentação do [auto-shop-system](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/blob/develop/docs/architecture/diagramas-fase-3.md).

- [RFC-0003: CPF, JWT RS256, KMS e JWKS](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/blob/develop/docs/rfc/RFC-0003-autenticacao-cliente-cpf-jwt.md)
- [ADR-0064: autenticação de cliente](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/blob/develop/docs/architecture/decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md)
- [Justificativa do PostgreSQL e modelo ER](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/blob/develop/docs/architecture/justificativa-banco-postgresql.md)
