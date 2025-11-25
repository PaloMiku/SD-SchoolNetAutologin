pnpm build
rm -rf out/plugin || true
mkdir -p out/plugin
cp -r dist package.json plugin.json main.py README.md LICENSE out/plugin/
cd out
rm -rf sd-schoolnet-autologin.zip || true
zip -r sd-schoolnet-autologin.zip plugin
ls -la sd-schoolnet-autologin.zip