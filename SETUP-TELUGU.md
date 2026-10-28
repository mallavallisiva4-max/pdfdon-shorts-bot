# PDFDon Telugu Video Bot: Setup (తెలుగులో)

| రోజు (ఉదయం 10 గంటలు) | Video |
|---|---|
| సోమ, బుధ, శుక్ర | **Short** (1080×1920, సుమారు 30 సెకన్లు) |
| మంగళ, గురు | **పొడవైన tutorial** (1920×1080, సుమారు 5 నిమిషాలు, chapters తో) |

ప్రతిసారీ bot ఇవి చేస్తుంది:

1. `topics.yaml` నుండి తర్వాతి pdfdon.com tool ఎంచుకుంటుంది
2. Claude తో Telugu script, title, description, tags రాయిస్తుంది
3. Telugu AI voice (Microsoft Edge voice; అది పని చేయకపోతే Google voice) తో narration తయారు చేస్తుంది
4. pdfdon.com ని నిజమైన browser లో తెరిచి **screen record** చేస్తుంది: cursor కదులుతుంది, sample photo upload అవుతుంది, అక్షరాలు type అవుతాయి, button నొక్కుతుంది
5. Video + thumbnail తయారు చేస్తుంది
6. YouTube కి **Public** గా upload చేస్తుంది. ఏదైనా step తప్పితే **Private** గా ఉంచుతుంది

⚠️ **పొడవైన videos కి `ANTHROPIC_API_KEY` తప్పనిసరి** (Step 3). Key లేకపోతే మంగళ, గురు runs "Long video skipped" అని ఆగిపోతాయి. Shorts మాత్రం key లేకపోయినా వస్తాయి.

**చేతితో run చేయడం:** Actions → PDFDon Shorts → Run workflow → **Video type** (short / long), **Test only**, **Topic id** ఎంచుకోండి.

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

1. **console.anthropic.com** లో login అవ్వండి → **Billing** లో credits జోడించండి (Short కి సుమారు ₹5-10, పొడవైన video కి సుమారు ₹15-30 ఖర్చు)
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

## Step 4: YouTube auto upload (ఒక్కసారి చేస్తే చాలు, సుమారు 20 నిమిషాలు)

Bot ప్రతి video ని **Private** గా upload చేస్తుంది. YouTube Studio లో చూసి, బాగుంటే మీరే **Public** చేయండి.
ఒక రోజుకు upload limit ఉంటుంది, కానీ వారానికి 3 videos కి అది సరిపోతుంది.

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

### 4d. Upload test
**Actions → PDFDon Shorts → Run workflow** → **Test only ☐ (tick తీసేయండి)** → Run.
అయ్యాక YouTube Studio → **Content** లో కొత్త video **Private** గా కనిపించాలి.

Secrets పెట్టిన తర్వాత ప్రతి video YouTube Studio లో **Private** గా వస్తుంది. Run page summary లో Studio link ఉంటుంది. చూసి, బాగుంటే **Public** చేయండి.

---

## Step 5: అన్ని భాషల్లో (subtitles + అనువాద titles)

ప్రతి video తో bot ఇవి కూడా పంపుతుంది:
- **Telugu subtitles**: ఎప్పుడూ. Viewers ⚙️ → Subtitles → **Auto-translate** తో ఏ భాషలో అయినా చదవొచ్చు
- **English subtitles**: `ANTHROPIC_API_KEY` ఉంటే
- **Title, description** English, Hindi, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati లో: `ANTHROPIC_API_KEY` ఉంటే. ఎవరి YouTube ఏ భాషలో ఉంటే వాళ్ళకు ఆ title కనిపిస్తుంది

Subtitles upload చేయడానికి YouTube కి ఇంకో permission (`youtube.force-ssl`) కావాలి. అందుకే **కొత్త refresh token** ఒక్కసారి తీసుకోవాలి:

1. **developers.google.com/oauthplayground** → ⚙️ → **Use your own OAuth credentials** → Client ID, Secret paste
2. ఎడమ వైపు **Input your own scopes** box లో ఈ రెండూ, మధ్యలో ఒక space తో paste చేయండి:
   ```
   https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl
   ```
3. **Authorize APIs** → Gmail → (Advanced → Go to PDFDon Shorts Bot) → రెండు permissions కి **Continue**
4. **Exchange authorization code for tokens** → కొత్త **Refresh token** copy చేయండి
5. GitHub → Settings → Secrets and variables → Actions → `YT_REFRESH_TOKEN` పక్కన ✏️ → కొత్త token paste → **Update secret**

ఇది చేయకపోయినా videos upload అవుతాయి. Subtitles మాత్రం "not added (403)" అని log లో వస్తుంది.

**Audio dubbing (voice వేరే భాషలో):** ఇది bot చేయలేదు. YouTube Studio → **Settings → Upload defaults → Advanced settings** లో **automatic dubbing** option కనిపిస్తే on చేయండి. ఆ option అన్ని channels కి, అన్ని భాషలకు ఇంకా రాలేదు.

## మార్పులు చేయడం

| ఏమి మార్చాలి | ఎక్కడ |
|---|---|
| కొత్త tool topic జోడించడం | `topics.yaml` లో ఒక entry copy చేసి మార్చండి |
| ఆడ voice | `bot/voice.py` లో `te-IN-MohanNeural` ని `te-IN-ShrutiNeural` గా మార్చండి |
| రోజులు / సమయం | `.github/workflows/shorts.yml` లో `cron` line |
| ఒక topic మళ్ళీ చేయాలంటే | Run workflow లో **Topic id** box లో id (ఉదా: `gst-calculator`) |

`state/done.json` లో ఇప్పటివరకు చేసిన videos list ఉంటుంది. Bot దాన్ని దానంతట అదే update చేస్తుంది.
