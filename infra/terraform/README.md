# Terraform: lambda-auth

Este módulo prepara a Lambda e as permissões mínimas de execução. Ele pressupõe que a equipe de plataforma forneça a conta, a região, a rede privada, o segredo de conexão com o PostgreSQL e a chave RSA assimétrica do KMS.

## Recursos gerenciados

- Função AWS Lambda Python 3.12 e grupo de logs com retenção configurável.
- Role de execução restrita a gravar logs, ler o segredo indicado e assinar/publicar a chave pública KMS indicada.
- Permissões de interfaces de rede somente quando os IDs de sub-redes e grupos de segurança existentes forem informados.

O módulo não cria VPC, sub-redes, banco, segredo, chave KMS, API Gateway, rotas, integração HTTP ou permissão de invocação para uma API compartilhada. A equipe proprietária do API Gateway deve criar a integração e a permissão de invocação depois de validar o contrato. A configuração não declara backend remoto; o backend e o armazenamento de estado precisam ser definidos pela equipe de plataforma.

## Pré-requisitos de ativação

1. Confirmar conta AWS, partição e região de homologação com a equipe responsável pela conta.
2. Confirmar o endpoint/issuer, audience, `kid`, grupo e esquema da JWKS com os consumidores do JWT. Os valores do `terraform.tfvars.example` são marcadores, não um contrato aprovado.
3. Criar ou identificar o segredo do Secrets Manager com o conteúdo `{"DATABASE_URL":"postgresql://..."}`. Restringir a credencial do banco a `SELECT` do identificador de cliente/documento e garantir que a rede da Lambda alcance o banco.
4. Criar ou identificar uma chave KMS RSA compatível com RSASSA-PKCS1-v1_5 SHA-256; a chave privada permanece no KMS. A política da chave também deve permitir `kms:Sign` e `kms:GetPublicKey` para a role criada aqui. Se o segredo do PostgreSQL usar uma chave KMS gerenciada pelo cliente, a política dessa chave deve permitir `kms:Decrypt` para a mesma role.
5. Confirmar sub-redes privadas e security group. A regra de saída deve permitir a conexão ao PostgreSQL e ao endpoint de Secrets Manager/KMS, por NAT ou VPC endpoints; o security group do banco deve aceitar PostgreSQL da Lambda.
6. Gerar o pacote para Linux x86_64 com as dependências de produção e fornecer o caminho `lambda_package_path`.
7. Fazer uma estimativa de custo na AWS Pricing Calculator com região e volume aprovados, incluindo invocações/duração/memória da Lambda, chamadas e armazenamento de logs, chamadas de assinatura KMS, segredo mensal e leituras do Secrets Manager, tráfego de rede e eventuais NAT gateways/VPC endpoints compartilhados. Conta, região, tráfego e arquitetura de rede não foram definidos; portanto não há estimativa numérica aprovada neste momento. Definir alarmes de orçamento antes da ativação.

Nenhum desses pré-requisitos foi criado ou consultado na AWS por esta implementação.

## Empacotar localmente

Use Python 3.12 em Linux compatível com AWS Lambda x86_64. A instalação em uma pasta de staging inclui o pacote e as dependências nativas necessárias:

```bash
mkdir -p dist
python3.12 -m pip install --no-compile --target build/lambda .
(cd build/lambda && zip -q -r ../../dist/lambda-auth.zip .)
```

Confirme que `lambda_auth/handler.py`, `psycopg` e `cryptography` estão na raiz do zip. Em Windows, empacote dentro de uma imagem Linux compatível com Lambda para não incluir wheels nativos incompatíveis.

## Validação estática

Copie `terraform.tfvars.example` para um arquivo local `terraform.tfvars` e preencha apenas valores aprovados. Para revisão da configuração, use:

```bash
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate -no-color
```

O job `terraform-static-validation` executa esses comandos sem credenciais AWS, sem backend remoto e sem gerar plano ou aplicar recursos. O arquivo de lock do provider deve ser revisado e versionado após o primeiro `terraform init` controlado.

## Inventário e remoção

Antes da ativação, registre em documentação operacional o dono e o identificador de cada dependência externa (conta, região, VPC, sub-redes, grupos de segurança, PostgreSQL, segredo, chave KMS e API Gateway), além do volume esperado, retenção de logs, estimativa de custo e orçamento. O IAM de rede inclui ações EC2 em `*`, limitação exigida por operações de interface de rede da Lambda; as demais permissões são limitadas aos ARNs fornecidos.

Para remover apenas os recursos pertencentes a este módulo, use o mesmo estado Terraform revisado para planejar e aplicar a destruição da função, role, policy e grupo de logs. Não remova as dependências compartilhadas. Revogue separadamente a política da chave KMS que referencia a role, se ela tiver sido adicionada à política da chave. A remoção requer uma janela aprovada pela equipe de plataforma e não foi executada.
