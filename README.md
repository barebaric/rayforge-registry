# Rayforge Package Registry

Welcome! This is the official registry for Rayforge packages.
The registry is a directory of plugins and assets that can be installed from
within the Rayforge laser cutting app.

## Publishing Your Release

When you are ready to publish a package, follow these steps:


### Step 1: Create your package as a GitHub repository

Ensure that you use our template, because it sets up the repository
structure and metadata file that the registry expects.

```bash
git clone https://github.com/barebaric/rayforge-addon-template.git
```

Then adapt to create your package!


### Step 2: Request your repository to be listed

This is a one-time step. Simply [edit allowed-repositories.yaml](allowed-repositories.yaml)
by adding your repository.


### Step 3: Done. Your packages are now released whenever you push a version tag

Publishing is as simple as pushing a Git tag.

```bash
# Commit all your changes first
git add .
git commit -m "Add new feature for v1.1.0"

# Create and push a semantic version tag (e.g., vX.Y.Z)
git tag v1.1.0
git push origin v1.1.0
```

That's it! No token or secret is needed. A scheduled workflow in this
repository ([poll-releases.yml](.github/workflows/poll-releases.yml)) polls
every listed repository hourly for new version tags. When it finds one, it
downloads your `rayforge-addon.yaml`, validates it, and publishes the new
version: trusted repositories are pushed directly, and new community
repositories are published through an automated pull request that is
merged automatically once CI validation passes.


## Addon Details: Long Description and Screenshots

When a user clicks an addon in Rayforge's addon manager, a detail view
opens with a longer description and screenshots. Both are optional and
declared in your `rayforge-addon.yaml`:

```yaml
long_description: |
  A longer description of what your addon does, written in Markdown.
  It is shown in the addon detail view, below the screenshots.

screenshots:
  - docs/screenshots/overview.png
  - docs/screenshots/settings.png
```

Rules:

- `long_description` is Markdown with at most 2000 characters. Headings,
  lists, emphasis, links, and code blocks are supported.
- `screenshots` lists up to 5 repo-relative paths to PNG, JPEG, or WebP
  images. Absolute paths and URLs are not allowed.
- Each image must be at most 3 MB.

The images must be committed to your repository. When a release is
published, the registry resolves each path to a raw GitHub URL pinned to
the release tag and verifies that it can be downloaded. Releases with
missing or invalid screenshots are rejected, so keep the files in place
for every tag you publish.
