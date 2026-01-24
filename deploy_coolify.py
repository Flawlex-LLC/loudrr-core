#!/usr/bin/env python3
"""
Loudrr Coolify Deployment Script

This script deploys the full Loudrr stack to Coolify via API.
All secrets are stored securely in Coolify (encrypted at rest), NOT in git.

Usage:
    1. Set environment variables:
       - COOLIFY_API_TOKEN: Your Coolify API token
       - COOLIFY_URL: Your Coolify instance URL (e.g., https://coolify.example.com)
       - COOLIFY_SERVER_UUID: Your server UUID from Coolify
       - COOLIFY_PROJECT_UUID: (optional) Existing project UUID

    2. Set app secrets (will be stored in Coolify):
       - SECRET_KEY: Django secret key
       - TELEGRAM_BOT_TOKEN: Telegram bot token
       - TWEETSCOUT_API_KEY: TweetScout API key
       - TWITTER_API_KEY: Twitter API key

    3. Run: python deploy_coolify.py

Environment variables can be in .env file (not committed to git).
"""

import os
import sys
import json
import secrets
import string
import requests
from urllib.parse import urljoin

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class CoolifyDeployer:
    def __init__(self):
        self.api_token = os.environ.get("COOLIFY_API_TOKEN")
        self.base_url = os.environ.get("COOLIFY_URL", "").rstrip("/")
        self.server_uuid = os.environ.get("COOLIFY_SERVER_UUID")
        self.project_uuid = os.environ.get("COOLIFY_PROJECT_UUID")

        # App domains
        self.api_domain = os.environ.get("API_DOMAIN", "api.loudrr.com")
        self.app_domain = os.environ.get("APP_DOMAIN", "app.loudrr.com")

        # GitHub repo
        self.github_repo = "MamoonThufail/engagement-bot"
        self.github_branch = "main"

        # Validate required env vars
        if not self.api_token:
            print("ERROR: COOLIFY_API_TOKEN not set")
            sys.exit(1)
        if not self.base_url:
            print("ERROR: COOLIFY_URL not set")
            sys.exit(1)
        if not self.server_uuid:
            print("ERROR: COOLIFY_SERVER_UUID not set")
            sys.exit(1)

        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Track created resources
        self.db_uuid = None
        self.db_password = None
        self.redis_uuid = None
        self.backend_uuid = None
        self.frontend_uuid = None
        self.bot_uuid = None

    def api_request(self, method, endpoint, data=None):
        """Make API request to Coolify."""
        url = urljoin(self.base_url + "/", f"api/v1/{endpoint}")

        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unknown method: {method}")

            if response.status_code >= 400:
                print(f"API Error ({response.status_code}): {response.text}")
                return None

            if response.text:
                return response.json()
            return {"success": True}

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None

    def generate_password(self, length=32):
        """Generate a secure random password."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def get_or_create_project(self):
        """Get existing project or create new one."""
        if self.project_uuid:
            print(f"Using existing project: {self.project_uuid}")
            return self.project_uuid

        print("Creating new project...")
        result = self.api_request("POST", "projects", {
            "name": "Loudrr",
            "description": "Loudrr - Attention Marketplace"
        })

        if result and "uuid" in result:
            self.project_uuid = result["uuid"]
            print(f"Created project: {self.project_uuid}")
            return self.project_uuid

        print("Failed to create project")
        return None

    def create_environment(self):
        """Create production environment in project."""
        print("Creating production environment...")
        result = self.api_request("POST", f"projects/{self.project_uuid}/environments", {
            "name": "production"
        })

        if result and "uuid" in result:
            self.env_uuid = result["uuid"]
            print(f"Created environment: {self.env_uuid}")
            return self.env_uuid

        # May already exist
        print("Environment may already exist, continuing...")
        return None

    def deploy_postgresql(self):
        """Deploy PostgreSQL database."""
        print("\n" + "="*50)
        print("Deploying PostgreSQL Database...")
        print("="*50)

        self.db_password = self.generate_password()

        result = self.api_request("POST", "databases", {
            "server_uuid": self.server_uuid,
            "project_uuid": self.project_uuid,
            "type": "postgresql",
            "name": "loudrr-db",
            "postgres_user": "loudrr",
            "postgres_password": self.db_password,
            "postgres_db": "loudrr",
            "image": "postgres:15-alpine",
            "is_public": False,
            "instant_deploy": True,
        })

        if result and "uuid" in result:
            self.db_uuid = result["uuid"]
            print(f"PostgreSQL deployed: {self.db_uuid}")
            print(f"Internal URL: postgresql://loudrr:{self.db_password}@{self.db_uuid}:5432/loudrr")
            return True

        print("Failed to deploy PostgreSQL")
        return False

    def deploy_redis(self):
        """Deploy Redis cache."""
        print("\n" + "="*50)
        print("Deploying Redis...")
        print("="*50)

        result = self.api_request("POST", "databases", {
            "server_uuid": self.server_uuid,
            "project_uuid": self.project_uuid,
            "type": "redis",
            "name": "loudrr-redis",
            "image": "redis:7-alpine",
            "is_public": False,
            "instant_deploy": True,
        })

        if result and "uuid" in result:
            self.redis_uuid = result["uuid"]
            print(f"Redis deployed: {self.redis_uuid}")
            return True

        print("Failed to deploy Redis")
        return False

    def deploy_backend(self):
        """Deploy Django backend API."""
        print("\n" + "="*50)
        print("Deploying Django Backend...")
        print("="*50)

        # Get secrets from environment (these will be stored in Coolify)
        secret_key = os.environ.get("SECRET_KEY") or self.generate_password(50)
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        tweetscout_key = os.environ.get("TWEETSCOUT_API_KEY", "")
        twitter_key = os.environ.get("TWITTER_API_KEY", "")

        # Build database URL using internal docker network
        database_url = f"postgresql://loudrr:{self.db_password}@loudrr-db:5432/loudrr"
        redis_url = "redis://loudrr-redis:6379/0"

        result = self.api_request("POST", "applications", {
            "server_uuid": self.server_uuid,
            "project_uuid": self.project_uuid,
            "name": "loudrr-backend",
            "git_repository": f"https://github.com/{self.github_repo}",
            "git_branch": self.github_branch,
            "build_pack": "dockerfile",
            "dockerfile": "backend/Dockerfile",
            "dockerfile_location": "/backend/Dockerfile",
            "base_directory": "/backend",
            "ports_exposes": "8000",
            "domains": self.api_domain,
            "instant_deploy": False,
        })

        if not result or "uuid" not in result:
            print("Failed to create backend application")
            return False

        self.backend_uuid = result["uuid"]
        print(f"Backend app created: {self.backend_uuid}")

        # Set environment variables (stored encrypted in Coolify)
        print("Setting backend environment variables...")
        env_vars = {
            "SECRET_KEY": secret_key,
            "DEBUG": "False",
            "DATABASE_URL": database_url,
            "REDIS_URL": redis_url,
            "ALLOWED_HOSTS": f"{self.api_domain},localhost",
            "CORS_ALLOWED_ORIGINS": f"https://{self.app_domain},https://loudrr.com",
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TWEETSCOUT_API_KEY": tweetscout_key,
            "TWITTER_API_KEY": twitter_key,
            "MINIAPP_URL": f"https://{self.app_domain}",
        }

        for key, value in env_vars.items():
            self.api_request("POST", f"applications/{self.backend_uuid}/envs", {
                "key": key,
                "value": value,
                "is_build_time": False,
            })

        print("Backend environment configured")
        return True

    def deploy_frontend(self):
        """Deploy Next.js frontend."""
        print("\n" + "="*50)
        print("Deploying Next.js Frontend...")
        print("="*50)

        result = self.api_request("POST", "applications", {
            "server_uuid": self.server_uuid,
            "project_uuid": self.project_uuid,
            "name": "loudrr-frontend",
            "git_repository": f"https://github.com/{self.github_repo}",
            "git_branch": self.github_branch,
            "build_pack": "dockerfile",
            "dockerfile": "frontend/Dockerfile",
            "dockerfile_location": "/frontend/Dockerfile",
            "base_directory": "/frontend",
            "ports_exposes": "3000",
            "domains": self.app_domain,
            "instant_deploy": False,
        })

        if not result or "uuid" not in result:
            print("Failed to create frontend application")
            return False

        self.frontend_uuid = result["uuid"]
        print(f"Frontend app created: {self.frontend_uuid}")

        # Set environment variables
        print("Setting frontend environment variables...")
        self.api_request("POST", f"applications/{self.frontend_uuid}/envs", {
            "key": "NEXT_PUBLIC_API_URL",
            "value": f"https://{self.api_domain}",
            "is_build_time": True,
        })

        print("Frontend environment configured")
        return True

    def deploy_bot(self):
        """Deploy Telegram bot worker."""
        print("\n" + "="*50)
        print("Deploying Telegram Bot Worker...")
        print("="*50)

        # Get secrets from environment
        secret_key = os.environ.get("SECRET_KEY") or self.generate_password(50)
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        tweetscout_key = os.environ.get("TWEETSCOUT_API_KEY", "")
        twitter_key = os.environ.get("TWITTER_API_KEY", "")

        database_url = f"postgresql://loudrr:{self.db_password}@loudrr-db:5432/loudrr"
        redis_url = "redis://loudrr-redis:6379/0"

        result = self.api_request("POST", "applications", {
            "server_uuid": self.server_uuid,
            "project_uuid": self.project_uuid,
            "name": "loudrr-bot",
            "git_repository": f"https://github.com/{self.github_repo}",
            "git_branch": self.github_branch,
            "build_pack": "dockerfile",
            "dockerfile": "backend/Dockerfile",
            "dockerfile_location": "/backend/Dockerfile",
            "base_directory": "/backend",
            "custom_docker_run_options": "--entrypoint python",
            "start_command": "python manage.py run_telegram_bot",
            "instant_deploy": False,
        })

        if not result or "uuid" not in result:
            print("Failed to create bot application")
            return False

        self.bot_uuid = result["uuid"]
        print(f"Bot app created: {self.bot_uuid}")

        # Set environment variables
        print("Setting bot environment variables...")
        env_vars = {
            "SECRET_KEY": secret_key,
            "DEBUG": "False",
            "DATABASE_URL": database_url,
            "REDIS_URL": redis_url,
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TWEETSCOUT_API_KEY": tweetscout_key,
            "TWITTER_API_KEY": twitter_key,
            "MINIAPP_URL": f"https://{self.app_domain}",
        }

        for key, value in env_vars.items():
            self.api_request("POST", f"applications/{self.bot_uuid}/envs", {
                "key": key,
                "value": value,
                "is_build_time": False,
            })

        print("Bot environment configured")
        return True

    def trigger_deployments(self):
        """Trigger deployments for all applications."""
        print("\n" + "="*50)
        print("Triggering Deployments...")
        print("="*50)

        apps = [
            ("Backend", self.backend_uuid),
            ("Frontend", self.frontend_uuid),
            ("Bot", self.bot_uuid),
        ]

        for name, uuid in apps:
            if uuid:
                print(f"Deploying {name}...")
                result = self.api_request("POST", f"applications/{uuid}/deploy")
                if result:
                    print(f"  {name} deployment triggered")
                else:
                    print(f"  Failed to trigger {name} deployment")

    def print_summary(self):
        """Print deployment summary."""
        print("\n" + "="*50)
        print("DEPLOYMENT SUMMARY")
        print("="*50)
        print(f"""
Resources Created:
- PostgreSQL: {self.db_uuid or 'Failed'}
- Redis: {self.redis_uuid or 'Failed'}
- Backend: {self.backend_uuid or 'Failed'}
- Frontend: {self.frontend_uuid or 'Failed'}
- Bot: {self.bot_uuid or 'Failed'}

URLs (after DNS configured):
- API: https://{self.api_domain}
- App: https://{self.app_domain}
- Health Check: https://{self.api_domain}/health/

Next Steps:
1. Configure DNS A records pointing to your Hetzner server
2. Wait for SSL certificates to provision (automatic)
3. Run migrations:
   coolify execute {self.backend_uuid} "python manage.py migrate"
4. Create superuser:
   coolify execute {self.backend_uuid} "python manage.py createsuperuser"
5. Test: /start command in Telegram bot

Database credentials (stored securely in Coolify):
- User: loudrr
- Database: loudrr
- Password: {self.db_password[:8]}... (truncated for security)
""")

    def deploy(self):
        """Run full deployment."""
        print("="*50)
        print("LOUDRR COOLIFY DEPLOYMENT")
        print("="*50)
        print(f"Coolify URL: {self.base_url}")
        print(f"Server UUID: {self.server_uuid}")
        print(f"API Domain: {self.api_domain}")
        print(f"App Domain: {self.app_domain}")

        # Create project
        if not self.get_or_create_project():
            print("Deployment failed: Could not create project")
            return False

        # Deploy databases first
        if not self.deploy_postgresql():
            print("Deployment failed: PostgreSQL")
            return False

        if not self.deploy_redis():
            print("Deployment failed: Redis")
            return False

        # Deploy applications
        if not self.deploy_backend():
            print("Deployment failed: Backend")
            return False

        if not self.deploy_frontend():
            print("Deployment failed: Frontend")
            return False

        if not self.deploy_bot():
            print("Deployment failed: Bot")
            return False

        # Trigger deployments
        self.trigger_deployments()

        # Print summary
        self.print_summary()

        print("\nDeployment initiated successfully!")
        return True


def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║              LOUDRR COOLIFY DEPLOYMENT SCRIPT                  ║
║                                                                ║
║  All secrets will be stored securely in Coolify               ║
║  (encrypted at rest) - NOT in git                              ║
╚═══════════════════════════════════════════════════════════════╝
""")

    deployer = CoolifyDeployer()
    success = deployer.deploy()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
