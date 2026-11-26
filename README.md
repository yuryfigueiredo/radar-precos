# Radar de Preços: RTX 3060 12GB, SSDs e Memórias RAM 16GB DDR4 Gamer

Automação executada pelo GitHub Actions no seu PC Windows com runner self-hosted. Ela monitora os menores preços da NVIDIA GeForce RTX 3060 12GB avulsa, SSDs e memórias RAM 16GB DDR4 gamer e envia um resumo formatado para o seu e-mail; para rodar sem acompanhamento, o PC e o runner precisam estar ligados, conectados à internet e disponíveis.

---

## 🎯 O que este robô monitora?

1. **Placa de vídeo NVIDIA:**
   - **NVIDIA GeForce RTX 3060 12GB** avulsa *(Kabum, Terabyte, Pichau, Amazon, Mercado Livre)*
   - Aceita somente títulos com **12GB explícito**; rejeita RTX 3060 8GB, outras placas, PCs montados, kits e acessórios.

2. **Memórias RAM Gamer:**
   - Memórias RAM **16GB DDR4 Gamer** (Desktop) mais baratas *(Kabum, Terabyte, Pichau, Amazon, Mercado Livre)*
   - Destaque fixo para **Mancer Dantalion 16GB DDR4 3200MHz CL19**
   - Seleção de marcas preferidas: **Kingston Fury Beast, XPG Gammix D35, Corsair Vengeance LPX e Crucial**

3. **SSDs:**
   - SSDs de **512 GB** (e 480GB/500GB) mais baratos *(Kabum, Terabyte, Pichau, Amazon, Mercado Livre)*
   - SSDs de **1 TB** (e 960GB/1000GB) mais baratos *(Kabum, Terabyte, Pichau, Amazon, Mercado Livre)*
   - SSDs de **2 TB** (e 1,92TB/2000GB) mais baratos *(Kabum, Terabyte, Pichau, Amazon, Mercado Livre)*
   - Destaques NVMe de 1TB e 2TB: **Kingston NV3, WD Blue SN580 e Crucial P3 Plus**

---

## 📁 Pasta Oficial do Projeto:
`\Documents\Projetos Yury\Automações\Automações de busca de preço`

---

## 🚀 Como funciona com o runner do seu PC (GitHub Actions)

O projeto usa o **GitHub Actions** para disparar a automação nos horários programados (08:00 e 18:00, horário de Brasília) ou pelo botão **Run workflow**. A coleta e o envio do e-mail acontecem no **PC Windows cadastrado como runner self-hosted**, usando a conexão residencial. Se o PC ou o runner estiver desligado, a execução programada pode atrasar ou não ocorrer.

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
git commit -m "Radar de precos SSDs e Memoria RAM DDR4"
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
