# Rayforge Package Registry

Welcome! This is the official registry for Rayforge packages.
The registry is a directory of plugins and assets that can be installed from
within the Rayforge laser cutting app.

## Publishing Your Release

When you are ready to publish a package, follow these steps:


### Step 1: Create your package as a GitHub repository

Ensure that you use our template, because it includes the necessary GitHub
workflow to publish your package automatically.

```bash
git clone https://github.com/barebaric/rayforge-package-template.git
```

Then adapt to create your package!


### Step 2: Request your repository to be listed

This is a one-time step. Simply [edit allowed-repositories.yaml](allowed-repositories.yaml)
by adding your repository.


### Step 3: Set Up Release Token (One-Time Setup)

The automated release workflow needs a token to announce your releases.

1.  **Create a Personal Access Token (PAT):**

    - Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic).
    - Click **"Generate new token"** (classic).
    - Give it a name (e.g., `Rayforge Registry Announcer`).
    - Set an expiration date.
    - Under **"Select scopes,"** check only the box for **`repo`**.
    - Click **"Generate token"** and copy it.

2.  **Add the Token to Repository Secrets:**
    - Go to your repository's **Settings > Secrets and variables > Actions**.
    - Click **"New repository secret"**.
    - **Name:** `REGISTRY_ACCESS_TOKEN`
    - **Secret:** Paste your token.


### Step 4: Done. Your packages are now released whenever you push a version tag

Publishing is as simple as pushing a Git tag.

```bash
# Commit all your changes first
git add .
git commit -m "Add new feature for v1.1.0"

# Create and push a semantic version tag (e.g., vX.Y.Z)
git tag v1.1.0
git push origin v1.1.0
```

That's it! The GitHub Action in your repository will automatically submit
your new version to this central Rayforge Registry, which will pull your
package file and update the registry.yaml here in the repository.
