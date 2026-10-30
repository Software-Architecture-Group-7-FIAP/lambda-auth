# Terraform: lambda-auth

Requer Terraform CLI 1.9 ou superior. As validações de entrada comparam variáveis de ambiente e configuração, recurso suportado a partir dessa versão.

Este módulo descreve a preparação de uma função Lambda Python 3.12 e suas permissões mínimas de execução. A infraestrutura ainda não foi ativada. Conta, região, rede privada, banco, segredo, chave KMS e API Gateway dependem de definição e aprovação explícitas de seus proprietários.

## Inventário de recursos, dependências e propriedade

| Item | Situação e dependências | Proprietário operacional |
|---|---|---|
| Função Lambda `aws_lambda_function.function` | Gerenciada por este módulo; depende do pacote Linux x86_64, role e policy, log group, valores aprovados de configuração e acessibilidade de rede ao PostgreSQL, Secrets Manager e KMS. | Equipe da aplicação após aprovação de plataforma. |
| Parâmetro SSM `aws_ssm_parameter.function_arn` | Opcional; criado apenas quando se informa um caminho aprovado. Guarda o ARN como `String` não secreta e aceita somente os caminhos de HML e PRD descritos abaixo. | Equipe da aplicação e identidade autorizada a executar Terraform. |
| Role `aws_iam_role.function` e policy `aws_iam_role_policy.function` | Gerenciadas por este módulo. A policy permite gravar logs no grupo declarado, ler apenas o nome lógico de segredo configurado (incluindo seu sufixo gerado no ARN), chamar `kms:Sign` somente na chave ativa e `kms:GetPublicKey` nas chaves publicadas. As permissões EC2 de interface de rede são incluídas quando há sub-redes privadas e usam `*`, conforme exigido pelas operações de rede da Lambda. | Equipe da aplicação; revisão e aprovação da equipe de segurança/plataforma. |
| Grupo de logs `aws_cloudwatch_log_group.function` | Gerenciado por este módulo com retenção configurável. A Lambda precisa dele para iniciar e gravar logs. | Equipe da aplicação; retenção aprovada pela observabilidade/compliance. |
| Interfaces de rede da Lambda | Criadas e removidas pelo serviço Lambda quando `private_subnet_ids` e `security_group_ids` são configurados; exigem permissões EC2 na role. Não são recursos Terraform deste módulo. | Equipe de plataforma/rede proprietária da VPC e sub-redes. |
| Conta AWS, região e estado Terraform | Ainda não definidos. O backend remoto e o armazenamento/controle de acesso do estado são externos ao módulo; `terraform init -backend=false` não acessa nem configura um backend remoto. | Equipe de plataforma/cloud responsável pela conta e pelo estado. |
| VPC, sub-redes privadas, security groups e caminho de saída | Obrigatórios em HML/PRD e fornecidos por plataforma; apenas dev pode omitir a VPC. Os IDs devem corresponder ao contrato SSM `/auto-shop/staging/network/vpc-id`, `/network/workload-private-subnet-ids` e `/network/lambda-security-group-id`; o preflight do coordenador compara a configuração implantada com esses valores antes de abrir recursos de sessão. Precisam alcançar PostgreSQL, Secrets Manager e KMS por NAT ou VPC endpoints; custos de ambos não estão validados. O security group do banco precisa aceitar a origem da Lambda na porta PostgreSQL. | Equipe de plataforma/rede e proprietária do banco, conforme cada recurso. |
| PostgreSQL e credencial | Dependência externa. A credencial deve ter somente o acesso de leitura necessário ao identificador de cliente/documento. O módulo não cria nem migra banco ou usuário. | Equipe proprietária do banco/dados. |
| Segredo do Secrets Manager | Dependência externa identificada pelo nome estável `auto-shop/staging/hml/lambda-auth` ou `auto-shop/staging/prd/lambda-auth`; conteúdo esperado: `{"DATABASE_URL":"postgresql://..."}`. A Lambda resolve o nome no Secrets Manager em cada atualização de cache, sem depender do sufixo mutável do ARN. Se usar uma chave KMS gerenciada pelo cliente para criptografia, sua policy precisa conceder `kms:Decrypt` à role da Lambda. A aplicação mantém cache de 300 segundos por ambiente de execução, então leituras reais esperadas são menores que o limite conservador usado na estimativa abaixo. | Equipe proprietária de segurança/segredos; banco aprova a rotação e o ciclo de vida da credencial. |
| Chaves KMS assimétricas RSA | Dependências externas indicadas por ARN. A chave ativa permite assinatura RSASSA-PKCS1-v1_5 SHA-256 e publicação; as adicionais permitem somente `kms:GetPublicKey`. A policy da chave deve autorizar a role da Lambda. O módulo não cria nem altera chaves ou suas policies. | Equipe proprietária de criptografia/segurança. |
| API Gateway HTTP API, rota, integração e permissão de invocação | Dependência externa e não declarada no módulo. A equipe proprietária deve aprovar contrato/issuer, audience, `kid`, grupo, esquema JWKS, rota, integração com Lambda e permissão de invocação antes de criar esses recursos. | Equipe proprietária do API Gateway, com a equipe da aplicação. |
| Pacote de implantação | Artefato local/CI em `lambda_package_path`; deve conter `lambda_auth/handler.py` e dependências compatíveis com Linux x86_64. | Equipe da aplicação. |

Os documentos `terraform.tfvars.example` e README são preparação; seus valores não constituem aprovação nem contrato operacional. Não há backend remoto configurado.

## Contrato SSM por stage

`environment` aceita `hml`, `prd` ou `dev`. HML e PRD são os stages do contrato de aplicação. Com o nome base padrão `lambda-auth`, suas funções são `lambda-auth-hml` e `lambda-auth-prd`; `dev` é para configuração de desenvolvimento e pode omitir a VPC.

| Stage | Nome padrão da função | Parâmetro SSM | Origem CORS permitida |
|---|---|---|---|
| `hml` | `lambda-auth-hml` | `/auto-shop/staging/auth/customer-token/function-arn/hml` | `https://app-hml.oficina-workshop.com.br` |
| `prd` | `lambda-auth-prd` | `/auto-shop/staging/auth/customer-token/function-arn/prd` | `https://app.oficina-workshop.com.br` |

`function_arn_ssm_parameter_name` fica vazio por padrão, portanto o parâmetro não é criado sem uma decisão explícita. Quando habilitada, a publicação aceita somente os dois caminhos acima, ligados respectivamente a `hml` e `prd`; `dev` não pode publicar nesses contratos. O ARN não é segredo. A identidade que executa Terraform precisa das permissões SSM necessárias para criar, atualizar, etiquetar e remover o parâmetro; essas permissões não são adicionadas à role da Lambda. Se o parâmetro já existir, importe-o no state Terraform revisado antes de planejar alterações.

Cada stage deve usar seu próprio state Terraform para que os recursos coexistam. O módulo não configura backend remoto; a equipe de plataforma precisa aprovar e configurar o state antes de qualquer provisionamento. A configuração local do handler pode usar `DATABASE_URL` diretamente.

## Contrato JWT consumido pelo auto-shop-system

| Stage | `jwt_issuer` | `jwt_audience` | JWKS público |
|---|---|---|---|
| `hml` | `https://api.oficina-workshop.com.br` | `auto-shop-api` | `https://api.oficina-workshop.com.br/hml/.well-known/jwks.json` |
| `prd` | `https://api.oficina-workshop.com.br` | `auto-shop-api` | `https://api.oficina-workshop.com.br/prd/.well-known/jwks.json` |

O issuer é a raiz estável da API nos dois stages; o base path escolhe o JWKS e as chaves do stage. Configure `jwt_issuer` e `jwt_audience` com esses valores ao planejar cada função e mantenha `JWT_KID` alinhado ao `kid` ativo publicado pelo respectivo endpoint. O API Gateway remove o base path ao encaminhar a rota para a Lambda, que responde em `/.well-known/jwks.json`.

O módulo publica somente o ARN da função no SSM, quando `function_arn_ssm_parameter_name` é definido para o stage. Issuer, audience e URL do JWKS são configuração pública nos overlays Kubernetes do `auto-shop-system`; não são parâmetros SSM neste contrato.

## Configuração de rotação

`jwt_kms_key_arn` e `jwt_kid` identificam a única chave que assina tokens. `jwt_additional_public_keys` recebe objetos com `kid` e `kms_key_id` para as chaves que também precisam aparecer no JWKS durante uma transição. O Terraform serializa essa lista em `JWT_ADDITIONAL_PUBLIC_KEYS_JSON` e separa as permissões IAM: `kms:Sign` permanece restrito à ativa e `kms:GetPublicKey` cobre todas as publicadas.

Use a sequência operacional documentada no README principal: pré-publicar a chave nova, aguardar propagação/cache, trocar a ativa mantendo sobreposição e retirar a antiga somente depois da janela de validade. Nunca reutilize um `kid` para outro material de chave.
## Cenário numérico de custo mensal de referência

**Referência ilustrativa em us-east-1 (US East, N. Virginia), sem free tier ou créditos.** Premissas: 100.000 chamadas de autenticação/mês; Lambda com 256 MiB e duração média de 250 ms; uma operação RSA `Sign` por chamada usando uma chave RSA_3072 nova e dedicada; um segredo do Secrets Manager e até 100.000 leituras (limite conservador; o cache de 300 segundos por ambiente de execução reduz as leituras reais); uma solicitação HTTP API por chamada; 1 KiB de logs ingeridos por chamada e retenção de 14 dias. Preços unitários públicos consultados nas páginas oficiais abaixo; a conta final é arredondada.

O cenário considera somente `POST /auth/customer/token`. Ele exclui chamadas e tráfego de `GET /.well-known/jwks.json` e as chamadas `kms:GetPublicKey` que ocorrem na primeira consulta JWKS de cada ambiente de execução; o signer mantém essa chave pública em cache por ambiente. Volume JWKS e quantidade de ambientes não foram definidos e precisam entrar na estimativa real antes de qualquer aprovação.

| Serviço | Fórmula de referência | USD/mês aproximado |
|---|---|---:|
| Lambda solicitações | 100.000 / 1.000.000 × $0,20 | $0,02 |
| Lambda computação | 100.000 × 0,25 s × 0,25 GB × $0,0000166667/GB-s | $0,1042 |
| API Gateway HTTP API | 100.000 / 1.000.000 × $1,00 | $0,10 |
| KMS armazenamento da chave | 1 chave × $1,00/chave-mês | $1,00 |
| KMS operações RSA `Sign` | 100.000 / 10.000 × $0,15 | $1,50 |
| Secrets Manager armazenamento | 1 segredo × $0,40/segredo-mês | $0,40 |
| Secrets Manager leituras (pior caso) | 100.000 / 10.000 × $0,05 | $0,50 |
| CloudWatch Logs ingestão | 100.000 × 1 KiB = 0,1024 GB decimal; 0,1024 GB × $0,50/GB | $0,0512 |
| CloudWatch Logs armazenamento | 0,1024 GB × 14/30 mês × $0,03/GB-mês | $0,0014 |
| **Subtotal ilustrativo** | **Soma das linhas acima, sem benefícios de free tier/créditos** | **$3,68** |

Fontes oficiais de preços: [AWS Lambda](https://aws.amazon.com/lambda/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/), [AWS KMS](https://aws.amazon.com/kms/pricing/), [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/) e [CloudWatch](https://aws.amazon.com/cloudwatch/pricing/). As páginas de preços são variáveis por região e configuração; confirme os valores no momento da aprovação.

Este subtotal **não é aprovado nem all-in**. Ele exclui custos de rede ainda não validados, incluindo NAT, VPC endpoints e tráfego; banco de dados; transferência de dados; serviços compartilhados; impostos e suporte. A estimativa real exige conta, região, volume de tráfego e arquitetura/custos de rede fornecidos e aprovados pelos respectivos proprietários, além da validação na AWS Pricing Calculator.

## Checklist de ativação, sujeito a aprovação explícita

Não executar os itens abaixo nesta fase de preparação. Antes de qualquer ativação futura, registrar a aprovação dos responsáveis de conta/plataforma, segurança, banco/rede, API e aplicação:

1. Aprovar conta, partição, região, ambiente, proprietário do estado Terraform, backend remoto, controles de acesso e política de retenção do estado.
2. Aprovar contrato de autenticação: issuer, audience, `kid`, grupo, endpoint, rota HTTP, formato de resposta e esquema JWKS com todos os consumidores.
3. Aprovar VPC, sub-redes, security groups e caminho de rede ao PostgreSQL, Secrets Manager e KMS; revisar e aprovar custo de NAT/VPC endpoints e regras de entrada/saída.
4. Aprovar banco, endpoint e usuário de menor privilégio; aprovar conteúdo, rotação, criptografia e equipe dona do segredo. Para HML/PRD, manter os nomes lógicos de segredo definidos no contrato de database-infra. Aprovar também a policy de decrypt se houver chave KMS dedicada à criptografia do segredo.
5. Aprovar a chave KMS RSA dedicada, algoritmo compatível, política de chave concedendo somente as operações necessárias à role da Lambda, monitoramento, rotação aplicável e ciclo de vida.
6. Aprovar pacote Linux x86_64, memória, timeout, variáveis e retenção de logs. Rever IAM, política de invocação e exposição da rota. Se houver publicação do ARN em SSM, aprovar também o caminho e o escopo IAM da identidade Terraform.
7. Produzir estimativa real na AWS Pricing Calculator com conta/região/tráfego/rede aprovados; obter aprovação de orçamento e definir alarmes e responsáveis por responder.
8. Obter autorização explícita de mudança e janela operacional dos proprietários antes de qualquer credencial, chamada AWS, plano/aplicação, deploy ou teste de integração. Documentar plano de rollback e aprovar a sequência de remoção abaixo.

Esta fase é estritamente preparação estática: **é proibido chamar APIs AWS, usar ou configurar credenciais AWS, executar `terraform apply`, fazer deploy ou provisionar recursos, rodar testes de integração ou fechar a issue.** A validação Terraform permitida inicializa providers com `-backend=false`; os testes de contrato podem executar `command = plan` com provider AWS mockado, sem consultar uma conta ou estado AWS. A CI falha se encontrar variáveis de ambiente ou arquivos padrão com material/configuração de credenciais AWS.

## Empacotar localmente

Use Python 3.12 em Linux compatível com AWS Lambda x86_64. A instalação em uma pasta de staging inclui o pacote e as dependências nativas necessárias:

```bash
mkdir -p dist
python3.12 -m pip install --no-compile --target build/lambda .
(cd build/lambda && zip -q -r ../../dist/lambda-auth.zip .)
```

Confirme que `lambda_auth/handler.py`, `psycopg` e `cryptography` estão na raiz do zip. Em Windows, empacote dentro de uma imagem Linux compatível com Lambda para não incluir wheels nativos incompatíveis.

## Validação estática

Copie `terraform.tfvars.example` para um arquivo local `terraform.tfvars` apenas quando houver valores aprovados. Para revisão estática da configuração:

```bash
terraform fmt -check -recursive
terraform init -backend=false -input=false -lockfile=readonly
terraform validate -no-color
```

O job Terraform da CI é preparação estática somente: permissões GitHub `contents: read`, checkout com `persist-credentials: false`, bloqueio de material/configuração de credenciais AWS, `terraform init -backend=false`, formatação, validação e `terraform test`. Os testes executam planos de contrato com provider AWS mockado (`command = plan`), sem backend e sem chamadas às APIs AWS; portanto não geram plano contra uma conta ou estado AWS nem executam apply, deploy ou provisionamento. O lockfile do provider está versionado para fixar a versão e os checksums; revise-o ao atualizar a restrição do provider.

## Remoção e propriedade do teardown

Nenhuma remoção foi executada. Em uma mudança futura aprovada, a equipe de plataforma/estado deve coordenar janela e revisar o estado e plano de destruição; a equipe da aplicação executa a remoção apenas dos recursos deste módulo (função Lambda, role, policy, grupo de logs e o parâmetro SSM opcional) com o mesmo estado aprovado. A remoção do log group apaga os logs retidos, portanto requer aceite do proprietário de observabilidade/compliance.

Os proprietários externos removem ou alteram suas próprias dependências somente após aprovação: equipe de API Gateway para rota/integração/permissão; plataforma/rede para configuração de VPC e endpoints compartilhados; banco para usuário e credenciais; segurança para policy e chave KMS; e proprietário de segredos para segredo e rotação. Antes de excluir a chave, avaliar dependências de validação de tokens emitidos; antes de remover segredo/rede/banco, confirmar que nenhum consumidor depende deles. A role referenciada na policy da chave deve ser removida da policy pelo proprietário da chave. Não destruir recursos compartilhados como parte do estado deste módulo.
