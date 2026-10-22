# ⚡ Radar de Preços: PCs Montados, SSDs e Memórias RAM 16GB DDR4 Gamer

Automação 100% em nuvem que monitora os menores preços de computadores gamer prontos (com garantia), SSDs e memórias RAM gamer, enviando um resumo formatado para o seu e-mail **sem precisar estar com o computador ligado**.

---

## 🎯 O que este robô monitora?

1. **Computadores Montados e Prontos (com garantia):**
   - Placa de Vídeo de **8 GB** mais baratos *(Pichau, Terabyte, Kabum)*
   - Placa de Vídeo de **12 GB** mais baratos *(Pichau, Terabyte, Kabum)*
   - Placa de Vídeo de **16 GB** mais baratos *(Pichau, Terabyte, Kabum)*

2. **Memórias RAM Gamer:**
   - Memórias RAM **16GB DDR4 Gamer** (Desktop) mais baratas *(Kabum, Terabyte, Pichau, Amazon, Mercado Livre)*

3. **Peças / SSDs:**
   - SSDs de **512 GB** (e 480GB/500GB) mais baratos *(Pichau, Terabyte, Kabum, Amazon, Mercado Livre)*
   - SSDs de **1 TB** (e 960GB/1000GB) mais baratos *(Pichau, Terabyte, Kabum, Amazon, Mercado Livre)*

---

## 📁 Pasta Oficial do Projeto:
`C:\Users\Yury\Documents\Projetos Yury\Automações\Automações de busca de preço`

---

## 🚀 Como funciona 24/7 na Nuvem (GitHub Actions)

O projeto usa o **GitHub Actions** (gratuito). O GitHub "acorda" nos horários programados (ex: 08:00 e 18:00), roda o script em Python, extrai os menores preços, formata o e-mail em HTML e envia para a sua caixa de entrada.

---

## ⚙️ Configuração Passo a Passo

### Passo 1: Gerar a Senha de Aplicativo do Gmail
Para o robô conseguir enviar e-mails pelo Gmail com segurança:
1. Acesse sua Conta Google em: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Digite um nome (ex: `Robo Precos`) e clique em **Criar**.
3. Copie a senha gerada de 16 letras (ex: `abcd efgh ijkl mnop`).

---

### Passo 2: Subir o projeto para o GitHub
No terminal da pasta do projeto (`C:\Users\Yury\Documents\Projetos Yury\Automações\Automações de busca de preço`):

```bash
git init
git add .
git commit -m "Radar de precos PCs SSDs e Memoria RAM DDR4"
git branch -M main
# Substitua com a URL do seu repositório privado no GitHub:
git remote add origin https://github.com/SEU_USUARIO/radar-precos.git
git push -u origin main
```

---

### Passo 3: Cadastrar as Chaves Secretas no GitHub
No seu repositório no GitHub:
1. Vá em **Settings** > **Secrets and variables** > **Actions**.
2. Clique no botão verde **New repository secret** e adicione:
   * `SENDER_EMAIL`: seu e-mail do Gmail que vai enviar.
   * `SENDER_PASSWORD`: a senha de aplicativo de 16 letras do Passo 1.
   * `RECEIVER_EMAIL`: o e-mail que vai receber os alertas (pode ser o mesmo).

---

### Passo 4: Testar o disparo na hora
1. Vá na aba **Actions** no seu repositório no GitHub.
2. Clique no fluxo **"Monitoramento Automático de Preços"** à esquerda.
3. Clique no botão **"Run workflow"** > **Run workflow**.
4. Em 1 ou 2 minutos, o e-mail chegará com os preços mais baixos de cada categoria!

---

## 💻 Teste Local (Opcional)

Se quiser rodar direto no seu computador para testar:
```powershell
Set-Location "C:\Users\Yury\Documents\Projetos Yury\Automações\Automações de busca de preço"

# Ativar o ambiente virtual
.\.venv\Scripts\Activate.ps1

# Executar a busca
python main.py
```
*O resultado também ficará salvo no arquivo `ultimo_relatorio.html` que você pode abrir com 2 cliques no navegador.*
