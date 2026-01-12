# Deploy to Vercel - Quick Start Guide

## ✅ Pre-Deployment Checklist

- [x] Build works locally (`npm run build` succeeds)
- [x] All dependencies installed
- [x] Vercel configuration file (`vercel.json`) is set up
- [x] Backend URL configured (Railway: `voice-agent-production-58c7.up.railway.app`)

## 🚀 Deployment Steps

### Option 1: Deploy via Vercel CLI (Recommended for first-time setup)

1. **Install Vercel CLI** (if not already installed):
   ```bash
   npm install -g vercel
   ```

2. **Navigate to client directory**:
   ```bash
   cd client
   ```

3. **Login to Vercel**:
   ```bash
   vercel login
   ```
   - This will open your browser to authenticate

4. **Deploy to preview** (test first):
   ```bash
   vercel
   ```
   - Follow the prompts:
     - Set up and deploy? **Yes**
     - Which scope? (Select your account/team)
     - Link to existing project? **No** (for first deployment)
     - Project name? (Press Enter for default or enter a custom name)
     - Directory? **./** (current directory)
     - Override settings? **No**

5. **Deploy to production**:
   ```bash
   vercel --prod
   ```

### Option 2: Deploy via Vercel Dashboard (Git Integration)

1. **Push your code to GitHub/GitLab/Bitbucket** (if not already):
   ```bash
   git add .
   git commit -m "Ready for Vercel deployment"
   git push
   ```

2. **Go to Vercel Dashboard**:
   - Visit [vercel.com](https://vercel.com)
   - Sign in with your GitHub/GitLab/Bitbucket account

3. **Import Project**:
   - Click **"Add New..."** → **"Project"**
   - Select your repository
   - Configure the project:
     - **Framework Preset**: Vite (should auto-detect)
     - **Root Directory**: `client` ⚠️ **IMPORTANT: Set this to `client`**
     - **Build Command**: `npm run build` (should auto-detect)
     - **Output Directory**: `dist` (should auto-detect)
     - **Install Command**: `npm install` (should auto-detect)

4. **Deploy**:
   - Click **"Deploy"**
   - Wait for build to complete (usually 1-2 minutes)

## 📋 Configuration Summary

Your deployment is configured with:
- **Framework**: Vite
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Backend Proxy**: `/api/*` → `https://voice-agent-production-58c7.up.railway.app/api/*`

## 🔍 Post-Deployment

1. **Get your deployment URL**:
   - Vercel will provide a URL like: `https://your-project.vercel.app`
   - You can also add a custom domain in Vercel settings

2. **Test the deployment**:
   - Visit your Vercel URL
   - Try connecting to verify the API proxy works

3. **Check logs if issues occur**:
   - Go to your project in Vercel Dashboard
   - Click on the deployment → View logs

## 🐛 Troubleshooting

### Build fails
- Check Vercel build logs for specific errors
- Ensure all dependencies are in `package.json`
- Verify Node.js version (Vercel uses Node 18.x by default)

### API calls not working
- Verify Railway backend is accessible: `https://voice-agent-production-58c7.up.railway.app`
- Check CORS settings on your Railway backend
- Verify the rewrite rule in `vercel.json` is correct

### 404 errors
- Ensure Root Directory is set to `client` in Vercel settings
- Check that `dist` folder is being generated correctly

## 📝 Next Steps

After successful deployment:
1. Set up a custom domain (optional) in Vercel project settings
2. Configure environment variables if needed (Vercel Dashboard → Settings → Environment Variables)
3. Enable automatic deployments from Git (already enabled by default)

---

**Ready to deploy?** Choose Option 1 or Option 2 above! 🚀
