# Vercel Deployment Guide

This guide will help you deploy the Pipecat client frontend to Vercel.

## Prerequisites

1. A Vercel account (sign up at [vercel.com](https://vercel.com))
2. Git repository with your code
3. Node.js installed locally (for testing)

## Step 1: Install Dependencies

First, make sure all dependencies are installed:

```bash
cd client
npm install
```

## Step 2: Test Build Locally

Before deploying, test that the build works:

```bash
npm run build
```

This should create a `dist` folder with the built files.

## Step 3: Deploy to Vercel

### Option A: Deploy via Vercel CLI (Recommended)

1. Install Vercel CLI globally:
   ```bash
   npm i -g vercel
   ```

2. Login to Vercel:
   ```bash
   vercel login
   ```

3. Navigate to the client directory:
   ```bash
   cd client
   ```

4. Deploy:
   ```bash
   vercel
   ```
   
   Follow the prompts:
   - Set up and deploy? **Yes**
   - Which scope? (Select your account/team)
   - Link to existing project? **No** (for first deployment)
   - Project name? (Enter a name or press Enter for default)
   - Directory? **./** (current directory)
   - Override settings? **No**

5. For production deployment:
   ```bash
   vercel --prod
   ```

### Option B: Deploy via Vercel Dashboard

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click **"Add New..."** → **"Project"**
3. Import your Git repository
4. Configure the project:
   - **Framework Preset**: Vite
   - **Root Directory**: `client` (if deploying from monorepo root)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`
5. Click **"Deploy"**

## Step 4: Configure Environment Variables (if needed)

If your app needs environment variables:

1. Go to your project settings on Vercel
2. Navigate to **Settings** → **Environment Variables**
3. Add any required variables

## Step 5: Configure API Proxy (Important)

Since your client connects to `/api/offer`, you need to configure the API proxy in `vercel.json`:

1. Update the `rewrites` section in `vercel.json` with your actual backend URL:
   ```json
   {
     "rewrites": [
       {
         "source": "/api/(.*)",
         "destination": "https://your-backend-url.com/api/$1"
       }
     ]
   }
   ```

   Replace `https://your-backend-url.com` with your actual backend server URL.

2. Alternatively, if your backend is also on Vercel, you can use Vercel's serverless functions or configure it as a separate service.

## Step 6: Update Client Connection URL (if needed)

If your backend is deployed separately, you may need to update the connection URL in `src/index.tsx`:

```typescript
connectParams={{
  connectionUrl: process.env.VITE_API_URL || '/api/offer',
  // ... rest of config
}}
```

And add `VITE_API_URL` as an environment variable in Vercel.

## Troubleshooting

### Build Fails

- Check that all dependencies are in `package.json`
- Ensure TypeScript compiles without errors: `npm run build`
- Check Vercel build logs for specific errors

### API Connection Issues

- Verify the `rewrites` configuration in `vercel.json`
- Check that your backend server is accessible
- Ensure CORS is properly configured on your backend

### Environment Variables Not Working

- Remember that Vite requires `VITE_` prefix for client-side variables
- Redeploy after adding environment variables

## Continuous Deployment

Once connected to a Git repository, Vercel will automatically deploy:
- **Production**: On pushes to your main/master branch
- **Preview**: On pushes to other branches and pull requests

## Additional Resources

- [Vercel Documentation](https://vercel.com/docs)
- [Vite Deployment Guide](https://vitejs.dev/guide/static-deploy.html#vercel)
- [Vercel CLI Reference](https://vercel.com/docs/cli)
