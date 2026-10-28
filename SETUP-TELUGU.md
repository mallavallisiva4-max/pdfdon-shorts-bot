# PDFDon Telugu Shorts Bot: Setup (తెలుగులో)

ప్రతి **సోమ, బుధ, శుక్ర ఉదయం 10 గంటలకు** ఈ bot ఇవి చేస్తుంది:

1. `topics.yaml` నుండి తర్వాతి pdfdon.com tool ఎంచుకుంటుంది
2. Claude తో Telugu script, title, description, tags రాయిస్తుంది
3. Telugu AI voice (Microsoft Edge voice, free) తో narration తయారు చేస్తుంది
4. pdfdon.com tool ని phone size browser లో తెరిచి screenshots తీస్తుంది
5. 1080×1920 Short video + thumbnail తయారు చేస్తుంది
6. YouTube కి **Private** గా upload చేస్తుంది (keys పెట్టిన తర్వాత మాత్రమే)

---

## Step 1: GitHub లో repo తయారు చేయడం (5 నిమిషాలు)

1. **github.com** లో account తెరవండి (లేకపోతే Sign up చేయండి).
2. పైన కుడి వైపు **+** → **New repository**
   - Name: `pdfdon-shorts-bot`
   - **Private** ఎంచుకోండి
   - **Create repository** నొక్కండి
3. కొత్త repo page లో **uploading an existing file** link నొక్కండి.
4. మీ PC లో `pdfdon-shorts-bot` folder తెరిచి, **లోపల ఉన్నవన్నీ** (`.github`, `bot`, `assets`, `state`, `topics.yaml`, `requirements.txt`, ఈ file) select చేసి browser లోకి drag చేయండి.
5. కింద **Commit changes** నొక్కండి.

⚠️ `.github` folder upload అయిందో లేదో చూడండి. Repo లో `.github/workflows/shorts.yml` కనిపించాలి. కనిపించకపోతే:
**Add file → Create new file** నొక్కి, name లో `.github/workflows/shorts.yml` అని type చేసి, ఆ file లోని text మొత్తం paste చేసి **Commit** చేయండి.

## Step 2: మొదటి Test (keys ఏమీ అవసరం లేదు)

1. Repo లో పైన **Actions** tab → **I understand my workflows, go ahead and enable them**
2. ఎడమ వైపు **PDFDon Shorts** → కుడి వైపు **Run workflow**
3. **Test only** ✅ tick అలాగే ఉంచి → ఆకుపచ్చ **Run workflow** నొక్కండి
4. 5-8 నిమిషాలు ఆగండి. ✅ ఆకుపచ్చ tick వస్తే run నొక్కండి.
5. కింద **Artifacts** లో **short** download చేసి, zip తెరిచి `short.mp4` చూడండి.

API key లేకపోతే script `topics.yaml` లోని fixed steps నుండి వస్తుంది. Video, voice, screenshots అన్నీ సరిగ్గా వస్తున్నాయో ఈ test లో తెలుస్తుంది.

❌ ఎరుపు X వస్తే: run తెరిచి **Make the Short** step లో error screenshot తీసి Claude కి పంపండి.

## Step 3: Claude API key (మంచి scripts కోసం)

1. **console.anthropic.com** లో login అవ్వండి → **Billing** లో credits జోడించండి (ఒక video కి సుమారు ₹5-10 ఖర్చు)
2. **API Keys** → **Create Key** → name `pdfdon-bot` → key copy చేయండి
3. GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
   - Name: `ANTHROPIC_API_KEY`
   - Secret: copy చేసిన key paste చేయండి → **Add secret**

ఇప్పుడు Step 2 test మళ్ళీ run చేస్తే script Claude రాస్తుంది. Title, description, tags `script.json` లో ఉంటాయి.

## ఇప్పుడు bot ఎలా పని చేస్తుంది (YouTube keys లేకుండా)

సోమ, బుధ, శుక్ర ఉదయం 10 గంటలకు video తయారై GitHub లో ఉంటుంది:

1. **Actions** tab → తాజా run → **short** artifact download చేయండి
2. Phone లో YouTube app → **+** → video upload చేయండి
3. Title, description `script.json` నుండి copy చేయండి

ఇలా రోజుకు 2 నిమిషాల పని మాత్రమే. Video GitHub లో 14 రోజులు ఉంటుంది.

---

## Step 4: YouTube auto upload (optional, ఎక్కువ పని)

⚠️ **ముందు ఇది తెలుసుకోండి:** Google review (audit) చేయని API project నుండి upload అయిన videos **Private (locked)** అవుతాయి. వాటిని Public చేయలేరు. Auto upload పని చేయాలంటే Google కి audit form పంపి approve అవ్వాలి (కొన్ని రోజుల నుండి వారాలు పట్టవచ్చు). Approve అయ్యే వరకు పైన చెప్పిన manual upload వాడండి.

### 4a. Google Cloud project
1. **console.cloud.google.com** → పైన project list → **New Project** → name `pdfdon-shorts` → **Create**
2. **APIs & Services → Library** → `YouTube Data API v3` వెతకండి → **Enable**
3. **Google Auth Platform** (OAuth consent screen) → **Get started**
   - App name: `PDFDon Shorts Bot`, support email: మీ Gmail
   - Audience: **External** → contact email → **Create**
4. **Audience** page → **Publish app** → **Confirm**
   (ఇది చేయకపోతే key 7 రోజుల్లో expire అవుతుంది)
5. **Clients** → **Create client** → type **Web application**
   - Authorized redirect URIs → **Add URI**: `https://developers.google.com/oauthplayground`
   - **Create** → **Client ID**, **Client secret** copy చేసి notepad లో పెట్టుకోండి

### 4b. Refresh token (OAuth Playground)
1. **developers.google.com/oauthplayground** తెరవండి
2. కుడి పైన ⚙️ → **Use your own OAuth credentials** ✅ → Client ID, Client secret paste చేయండి
3. ఎడమ వైపు box లో ఇది type చేయండి: `https://www.googleapis.com/auth/youtube.upload` → **Authorize APIs**
4. మీ Gmail ఎంచుకోండి. "Google hasn't verified this app" వస్తే → **Advanced** → **Go to PDFDon Shorts Bot** (ఇది మీ సొంత app) → **Continue**
5. **Exchange authorization code for tokens** నొక్కండి → **Refresh token** copy చేయండి

### 4c. GitHub secrets
Step 3 లో లాగే ఈ మూడు secrets జోడించండి:

| Name | Value |
|---|---|
| `YT_CLIENT_ID` | Client ID |
| `YT_CLIENT_SECRET` | Client secret |
| `YT_REFRESH_TOKEN` | Refresh token |

### 4d. Audit form
**support.google.com/youtube/contact/yt_api_form** లో "YouTube API Services - Audit and Quota Extension Form" నింపండి. Use case: "Uploading my own educational Shorts to my own channel PDFDon Telugu (@pdfdontelugu)".

Secrets పెట్టిన తర్వాత ప్రతి video YouTube Studio లో **Private** గా వస్తుంది. Run page summary లో Studio link ఉంటుంది. చూసి, బాగుంటే **Public** చేయండి.

---

## మార్పులు చేయడం

| ఏమి మార్చాలి | ఎక్కడ |
|---|---|
| కొత్త tool topic జోడించడం | `topics.yaml` లో ఒక entry copy చేసి మార్చండి |
| ఆడ voice | `bot/voice.py` లో `te-IN-MohanNeural` ని `te-IN-ShrutiNeural` గా మార్చండి |
| రోజులు / సమయం | `.github/workflows/shorts.yml` లో `cron` line |
| ఒక topic మళ్ళీ చేయాలంటే | Run workflow లో **Topic id** box లో id (ఉదా: `gst-calculator`) |

`state/done.json` లో ఇప్పటివరకు చేసిన videos list ఉంటుంది. Bot దాన్ని దానంతట అదే update చేస్తుంది.
