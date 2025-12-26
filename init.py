import re
import shutil
import subprocess
import sys


def run_command(command, check=True, capture_output=False):
    try:
        result = subprocess.run(
            command,
            check=check,
            text=True,
            capture_output=capture_output,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            print(f"❌ Command failed: {' '.join(command)}")
            if e.stderr:
                print(e.stderr)
            sys.exit(1)
        return e


def get_config_value(key):
    try:
        with open("wrangler.toml", "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(rf'^{key}\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                return match.group(1)
    except FileNotFoundError:
        return None
    return None


def check_tool(tool_name):
    return shutil.which(tool_name) is not None


def main():
    print("🚀 Starting ByteGo initialization...")

    # 1. Check for npm
    if not check_tool("npm"):
        print("❌ npm is not installed. Please install Node.js and npm.")
        sys.exit(1)

    # 2. Install dependencies
    print("📦 Installing dependencies...")
    run_command(["npm", "install"], check=True)

    # 3. Check for wrangler
    if not check_tool("wrangler"):
        print("⚠️ Wrangler not found in PATH. Installing globally...")
        run_command(["npm", "install", "-g", "wrangler"], check=True)

    project_name = "bytego"

    # 4. Get Configuration
    cdn_domain = get_config_value("PUBLIC_DOMAIN")
    if cdn_domain:
        cdn_domain = cdn_domain.replace("https://", "").replace("/", "")
    else:
        print("⚠️  Could not detect PUBLIC_DOMAIN in wrangler.toml")
        try:
            cdn_domain = input(
                "👉 Please enter your R2 Custom Domain (e.g., cdn.example.com): "
            ).strip()
        except KeyboardInterrupt:
            sys.exit(1)

    # 5. Create R2 bucket
    print(f"🪣 Checking R2 bucket '{project_name}'...")
    # Ignore error if bucket exists
    run_command(
        ["wrangler", "r2", "bucket", "create", project_name],
        check=False,
        capture_output=True,
    )

    # 6. Set CORS
    print("🔒 Setting CORS for R2 bucket...")
    run_command(
        ["wrangler", "r2", "bucket", "cors", "set", project_name, "cors.json"],
        check=True,
    )

    # 7. Bind custom domain
    if cdn_domain:
        print(f"🔗 Binding custom domain {cdn_domain} to bucket...")
        res = run_command(
            ["wrangler", "r2", "bucket", "domain", "add", project_name, cdn_domain],
            check=False,
            capture_output=True,
        )
        if res.returncode != 0:
            print(
                f"   ⚠️  Domain binding returned code {res.returncode}. It might already be bound or require manual setup."
            )

    # 8. Deploy Worker
    print("☁️ Deploying Worker...")
    run_command(["wrangler", "deploy"], check=True)

    print("\n✅ Initialization & Deployment complete!")
    if cdn_domain:
        print(f"👉 Your CDN domain is: https://{cdn_domain}")
    print("🔑 Auth Key: Please set it via 'wrangler secret put AUTH_KEY'")
    print("💡 Tip: Run 'npm run deploy' for future updates.")


if __name__ == "__main__":
    main()
