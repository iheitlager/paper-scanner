# ReadTheDocs Deployment Guide

## Quick Start to Live Docs

### Step 1: Verify Configuration
```bash
# Check files are in place
ls -la mkdocs.yml .readthedocs.yml docs/requirements.txt

# Build locally to verify
mkdocs serve

# Visit http://localhost:8000
```

### Step 2: Push to GitHub
```bash
git add mkdocs.yml .readthedocs.yml docs/ docs/requirements.txt
git commit -m "docs: add mkdocs and readthedocs integration"
git push origin main
```

### Step 3: Connect to ReadTheDocs

1. **Visit ReadTheDocs**
   - Go to https://readthedocs.org
   - Sign in with GitHub account
   - Click "Import a Project"

2. **Import Your Repository**
   - Select "paper-scanner" from list
   - Or enter GitHub URL manually
   - Click "Next"

3. **Verify Settings**
   - Name: paper-scanner
   - Repository: https://github.com/iheitlager/paper-scanner
   - Default branch: main
   - Click "Finish"

4. **Configure Python Environment**
   - Go to Admin → Settings
   - Python version: 3.11
   - Build configuration: Use `.readthedocs.yml`
   - Save

5. **Trigger Initial Build**
   - Go to Build History
   - Click "Build version"
   - Watch build progress
   - Once complete, visit live documentation!

### Step 4: Enable GitHub Integration (Optional)

Connect GitHub to ReadTheDocs for automatic builds:

1. **In ReadTheDocs**
   - Admin → Integrations
   - Click GitHub integration link
   - Authorize ReadTheDocs

2. **In GitHub**
   - Repo Settings → Webhooks
   - Add webhook for pushes
   - ReadTheDocs automatically builds on each push

## URL Structure

Once live, documentation will be at:
```
https://paper-scanner.readthedocs.io/

Subpages:
- https://paper-scanner.readthedocs.io/en/latest/
- https://paper-scanner.readthedocs.io/en/latest/guide/installation/
- https://paper-scanner.readthedocs.io/en/latest/adr/0001-pipeline-architecture/
```

## Features Enabled

### Search
- Automatically indexed by ReadTheDocs
- Searchable within built documentation
- Accessible at `/en/latest/search/`

### Versions
- With `mike` installed in `docs/requirements.txt`
- Version selector available in top-right
- Can host multiple versions (stable, dev, etc.)

### Custom Domain (Optional)
1. In ReadTheDocs Admin → Domains
2. Add custom domain: `docs.paper-scanner.io`
3. Update DNS CNAME record
4. Verify and enable

## Customization Options

### Update GitHub Links
Edit `mkdocs.yml`:
```yaml
repo_url: https://github.com/iheitlager/paper-scanner
edit_uri: edit/main/docs/
```

Update to your actual GitHub organization/repo.

### Change Site Name
Edit `mkdocs.yml`:
```yaml
site_name: paper-scanner
site_description: Your custom description
```

### Add Analytics
Edit `mkdocs.yml`:
```yaml
extra:
  analytics:
    provider: google
    property: YOUR_GOOGLE_ANALYTICS_ID
```

### Custom CSS/JS
Add to `docs/stylesheets/` and `docs/javascripts/` directories.

## Troubleshooting

### Build Fails in ReadTheDocs

**Check the build logs:**
1. ReadTheDocs Admin → Build History
2. Click failed build
3. View "Build output" tab

**Common issues:**

1. **Missing dependencies**
   ```
   Error: No module named 'mkdocs_material'
   ```
   Solution: Ensure `docs/requirements.txt` is correct

2. **Python version mismatch**
   ```
   Error: Python 3.10 installed, but 3.11 required
   ```
   Solution: Check `.readthedocs.yml` python version

3. **Configuration error**
   ```
   Error: File mkdocs.yml not found
   ```
   Solution: Ensure `mkdocs.yml` is in repo root

### Documentation Not Updating

1. Clear ReadTheDocs cache
   - Admin → Builds
   - Click "Build version" again

2. Force rebuild
   ```bash
   # Push dummy commit to trigger rebuild
   git commit --allow-empty -m "trigger rebuild"
   git push
   ```

3. Check webhook
   - GitHub Repo → Settings → Webhooks
   - Verify ReadTheDocs webhook is listed
   - Test delivery if available

### Search Not Working

1. Ensure search plugin enabled in `mkdocs.yml`:
   ```yaml
   plugins:
     - search
   ```

2. Rebuild documentation

3. Give ReadTheDocs time to index (up to 24 hours)

## Updating Documentation

### Local Development
```bash
# Edit files in docs/
vim docs/guide/installation.md

# Test changes
mkdocs serve

# Commit changes
git add docs/guide/installation.md
git commit -m "docs: update installation guide"
git push origin main
```

### Automatic Deployment
Once connected to ReadTheDocs:
1. Push to main branch
2. ReadTheDocs automatically builds
3. Changes appear within minutes

### Staging Builds
For large changes, test on a branch:
```bash
git checkout -b docs/improvements
# ... make changes ...
git push origin docs/improvements
# ReadTheDocs can build this branch for preview
```

## Monitoring

### Build Status
- Check ReadTheDocs dashboard regularly
- Enable email notifications for build failures
- Monitor search functionality

### Analytics (Optional)
If Google Analytics enabled:
- Track documentation usage
- Find popular pages
- Identify missing content

### Feedback
- Add Disqus comments (optional)
- Collect user feedback
- Iterate on documentation

## Best Practices

### 1. Regular Updates
- Keep documentation in sync with code
- Update as features are added
- Remove outdated information

### 2. Clear Organization
- Use consistent heading structure
- Link related documents
- Provide navigation breadcrumbs

### 3. Examples
- Include code examples
- Show expected output
- Explain complex concepts

### 4. Maintenance
- Fix broken links
- Update outdated references
- Ensure code samples run

### 5. Community
- Welcome contributions
- Review documentation PRs
- Respond to feedback

## Advanced Topics

### Building Multiple Versions

Use `mike` for version management:
```bash
# List all doc versions
mike list

# Deploy version to docs
mike deploy 2.4.0 latest

# Set default version
mike set-default 2.4.0
```

### Custom Redirects

Create `.htaccess` or `_redirects` file:
```
# Redirect old doc URLs
/old-page/ -> /new-page/
```

### Integration with CI/CD

ReadTheDocs builds automatically on:
- Push to tracked branches
- Pull requests
- Manual builds from admin

## Support and Resources

- **ReadTheDocs Documentation**: https://docs.readthedocs.io
- **mkdocs Help**: https://www.mkdocs.org
- **Material Theme**: https://squidfunk.github.io/mkdocs-material
- **GitHub Help**: https://docs.github.com

## Deployment Checklist

- [ ] Files created:
  - [ ] `mkdocs.yml`
  - [ ] `.readthedocs.yml`
  - [ ] `docs/requirements.txt`
  - [ ] `docs/index.md`
  
- [ ] Documentation complete:
  - [ ] User guides
  - [ ] Architecture docs
  - [ ] API reference
  - [ ] Contributing guidelines
  - [ ] ADRs

- [ ] GitHub ready:
  - [ ] Repository URL correct
  - [ ] Main branch set
  - [ ] Files committed and pushed

- [ ] ReadTheDocs configured:
  - [ ] Project imported
  - [ ] Python 3.11 selected
  - [ ] Settings verified
  - [ ] Initial build successful

- [ ] Live and working:
  - [ ] Docs accessible at readthedocs.io
  - [ ] Search functional
  - [ ] Navigation works
  - [ ] Code examples visible

---

**Deployment Date**: 28 December 2025
**System**: mkdocs + Material Theme + ReadTheDocs
**Status**: Ready for production
