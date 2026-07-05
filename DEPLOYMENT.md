# Deployment guide — Streamlit Community Cloud (free)

This assumes zero prior experience with GitHub or Streamlit. Follow in order.

## Part 1 — Get a GitHub account and put the code there

1. Go to https://github.com and sign up for a free account if you don't
   already have one.
2. Once logged in, click the **+** icon top-right → **New repository**.
3. Name it something like `solar-blueprint-app`. Leave it **Public**
   (Streamlit Community Cloud's free tier requires a public repo to deploy
   from). Do not add a README, .gitignore, or license on this screen — you
   already have these files locally.
4. Click **Create repository**. GitHub will show you a page with setup
   instructions — keep that tab open, you'll need the repo URL from it.

### Uploading the code (no command line needed)

The easiest first-time path is GitHub's web upload:

1. On your new (empty) repo page, click **uploading an existing file**.
2. Drag the entire contents of the `solar-blueprint` folder into the
   browser window — all the `.py` files, `requirements.txt`, `README.md`,
   the `data` folder, and the `.streamlit` folder.
   - **Important**: make sure the `data/pricing_cache.csv` file and the
     `.streamlit/config.toml` file actually get uploaded — GitHub's drag-and-drop
     sometimes needs folders dragged in individually rather than the parent
     folder, depending on your browser. After uploading, click into the repo
     and confirm you see a `data` folder and a `.streamlit` folder, not just
     loose `.py` files.
3. Scroll down, add a commit message like "Initial commit", and click
   **Commit changes**.

*(If you're comfortable with the command line instead, the standard flow is
`git init`, `git add .`, `git commit -m "Initial commit"`, then
`git remote add origin <your-repo-url>` and `git push -u origin main` — but
the web upload above works just as well for a first deployment.)*

## Part 2 — Create a Streamlit Community Cloud account

1. Go to https://share.streamlit.io (or click "Sign up" from
   https://streamlit.io/cloud).
2. Sign up using **"Continue with GitHub"** — this is the easiest option
   since it lets Streamlit see your repos without a separate password.
3. Authorize Streamlit's GitHub app when prompted. You can choose to grant
   access to all repos or just the one you created — either is fine.

## Part 3 — Deploy the app

1. From the Streamlit Community Cloud dashboard, click **Create app** (or
   **New app**).
2. Choose **"Deploy a public app from GitHub"**.
3. Fill in the three fields:
   - **Repository**: select `your-username/solar-blueprint-app`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Click **Advanced settings** (optional but recommended):
   - You can set the Python version here if needed — 3.11 or 3.12 is safe.
   - You do not need to add any Secrets for this app, since there are no
     API keys anywhere in this build.
5. Click **Deploy**.

Streamlit will now build your app — it installs everything in
`requirements.txt` and starts the app. This usually takes 1-3 minutes the
first time. You'll see a live log; if something goes wrong, the error will
show here (see Troubleshooting below).

## Part 4 — Get your link and share it

Once deployed, your app is live at a URL like:

```
https://your-username-solar-blueprint-app-abc123.streamlit.app
```

You can find and copy this exact URL from the app's page on your Streamlit
dashboard, and optionally customize the subdomain via **Settings → General**
on the app's dashboard page.

This link is public — anyone with it can use the app. It will "sleep"
after a period of no visitors and take ~20-30 seconds to wake up on the
next visit; this is normal on the free tier.

## Part 5 — Making changes later

Whenever you want to update the app (e.g. refresh `pricing_cache.csv` with
real prices):

1. Go to your GitHub repo in the browser.
2. Click into the file you want to change (e.g. `data/pricing_cache.csv`).
3. Click the pencil (edit) icon, make your change, and commit it directly
   on GitHub.
4. Streamlit Community Cloud watches your repo and will automatically
   redeploy the app with your change within a minute or two. No separate
   "publish" step needed.

## Troubleshooting

- **"ModuleNotFoundError" in the deploy log**: double-check
  `requirements.txt` was actually uploaded to the repo root (not inside a
  subfolder).
- **"FileNotFoundError: data/pricing_cache.csv"**: the `data` folder didn't
  upload correctly. Go to your repo on GitHub and confirm the folder and
  file exist at `data/pricing_cache.csv` relative to the repo root.
- **App shows old content after you edited a file**: give it a minute —
  Community Cloud redeploys are not instant. You can also force it from
  your app's dashboard page via the **⋮ menu → Reboot app**.
- **You want to keep the code private**: Community Cloud's free tier
  requires a public repository for a free personal app. If you need
  privacy, that's the point where you'd move to a small paid tier or a
  different host — not necessary for a v1 you're testing.
