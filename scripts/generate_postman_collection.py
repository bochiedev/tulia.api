#!/usr/bin/env python3
"""
Generate Postman collection and environment for Tulia AI API.

Usage:
    python scripts/generate_postman_collection.py
"""
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def create_request(name, method, url, description="", body=None, headers=None):
    """Create a Postman request object."""
    request = {
        "name": name,
        "request": {
            "method": method,
            "header": headers or [
                {"key": "X-TENANT-ID", "value": "{{tenant_id}}", "type": "text"},
                {"key": "X-TENANT-API-KEY", "value": "{{tenant_api_key}}", "type": "text"}
            ],
            "url": {
                "raw": f"{{{{base_url}}}}{url}",
                "host": ["{{base_url}}"],
                "path": url.strip('/').split('/')
            },
            "description": description
        },
        "response": []
    }
    
    if body:
        request["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {
                "raw": {
                    "language": "json"
                }
            }
        }
    
    return request


def create_jwt_request(name, method, url, description="", body=None):
    """Create a request with JWT authentication."""
    headers = [
        {"key": "Authorization", "value": "Bearer {{jwt_token}}", "type": "text"},
        {"key": "Content-Type", "value": "application/json", "type": "text"}
    ]
    return create_request(name, method, url, description, body, headers)


def create_tenant_jwt_request(name, method, url, description="", body=None):
    """Create a request with both JWT and tenant headers."""
    headers = [
        {"key": "Authorization", "value": "Bearer {{jwt_token}}", "type": "text"},
        {"key": "X-TENANT-ID", "value": "{{tenant_id}}", "type": "text"},
        {"key": "Content-Type", "value": "application/json", "type": "text"}
    ]
    return create_request(name, method, url, description, body, headers)


def generate_collection():
    """Generate the complete Postman collection."""
    collection = {
        "info": {
            "name": "Tulia AI API",
            "description": "Multi-tenant WhatsApp commerce and services platform with comprehensive RBAC",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "_postman_id": "tulia-ai-collection",
            "version": "1.0.0"
        },
        "item": []
    }
    
    # Authentication folder
    auth_folder = {
        "name": "Authentication",
        "description": "User registration, login, and profile management",
        "item": [
            create_jwt_request(
                "Register",
                "POST",
                "/v1/auth/register",
                "Register a new user and create their first tenant",
                {
                    "email": "user@example.com",
                    "password": "SecurePassword123!",
                    "business_name": "My Business",
                    "first_name": "John",
                    "last_name": "Doe"
                }
            ),
            create_jwt_request(
                "Login",
                "POST",
                "/v1/auth/login",
                "Authenticate and receive JWT token",
                {
                    "email": "user@example.com",
                    "password": "SecurePassword123!"
                }
            ),
            create_jwt_request(
                "Get Profile",
                "GET",
                "/v1/auth/me",
                "Get current user profile"
            ),
            create_jwt_request(
                "Update Profile",
                "PUT",
                "/v1/auth/me",
                "Update user profile",
                {
                    "first_name": "Jane",
                    "last_name": "Smith"
                }
            ),
            create_jwt_request(
                "Verify Email",
                "POST",
                "/v1/auth/verify-email",
                "Verify email address with token",
                {
                    "token": "verification-token-here"
                }
            ),
            create_jwt_request(
                "Forgot Password",
                "POST",
                "/v1/auth/forgot-password",
                "Request password reset",
                {
                    "email": "user@example.com"
                }
            ),
            create_jwt_request(
                "Reset Password",
                "POST",
                "/v1/auth/reset-password",
                "Reset password with token",
                {
                    "token": "reset-token-here",
                    "new_password": "NewSecurePassword123!"
                }
            )
        ]
    }
    collection["item"].append(auth_folder)
    
    # Tenant Management folder
    tenant_folder = {
        "name": "Tenant Management",
        "description": "Tenant creation, listing, and member management",
        "item": [
            create_tenant_jwt_request(
                "List My Tenants",
                "GET",
                "/v1/tenants",
                "List all tenants where user has membership"
            ),
            create_tenant_jwt_request(
                "Create Tenant",
                "POST",
                "/v1/tenants",
                "Create a new tenant",
                {
                    "name": "New Business",
                    "slug": "new-business"
                }
            ),
            create_tenant_jwt_request(
                "Get Tenant Details",
                "GET",
                "/v1/tenants/{{tenant_id}}",
                "Get detailed tenant information"
            ),
            create_tenant_jwt_request(
                "List Tenant Members",
                "GET",
                "/v1/tenants/{{tenant_id}}/members",
                "List all members of a tenant"
            ),
            create_tenant_jwt_request(
                "Invite Member",
                "POST",
                "/v1/tenants/{{tenant_id}}/members",
                "Invite a user to join tenant (requires users:manage)",
                {
                    "email": "newmember@example.com",
                    "role_ids": ["role-uuid-here"]
                }
            )
        ]
    }
    collection["item"].append(tenant_folder)
    
    # Catalog folder
    catalog_folder = {
        "name": "Catalog",
        "description": "Product catalog management (requires catalog:view or catalog:edit)",
        "item": [
            create_request(
                "List Products",
                "GET",
                "/v1/catalog",
                "List all products (requires catalog:view)"
            ),
            create_request(
                "Get Product",
                "GET",
                "/v1/catalog/{{product_id}}",
                "Get product details (requires catalog:view)"
            ),
            create_request(
                "Create Product",
                "POST",
                "/v1/catalog",
                "Create a new product (requires catalog:edit)",
                {
                    "name": "New Product",
                    "description": "Product description",
                    "price": 99.99,
                    "currency": "USD",
                    "sku": "PROD-001",
                    "stock_quantity": 100
                }
            ),
            create_request(
                "Update Product",
                "PUT",
                "/v1/catalog/{{product_id}}",
                "Update product (requires catalog:edit)",
                {
                    "name": "Updated Product",
                    "price": 89.99
                }
            ),
            create_request(
                "Delete Product",
                "DELETE",
                "/v1/catalog/{{product_id}}",
                "Delete product (requires catalog:edit)"
            ),
            create_request(
                "Sync WooCommerce",
                "POST",
                "/v1/catalog/sync/woocommerce",
                "Sync products from WooCommerce (requires integrations:manage)"
            ),
            create_request(
                "Sync Shopify",
                "POST",
                "/v1/catalog/sync/shopify",
                "Sync products from Shopify (requires integrations:manage)"
            )
        ]
    }
    collection["item"].append(catalog_folder)
    
    # Orders folder
    orders_folder = {
        "name": "Orders",
        "description": "Order management (requires orders:view or orders:edit)",
        "item": [
            create_request(
                "List Orders",
                "GET",
                "/v1/orders",
                "List all orders (requires orders:view)"
            ),
            create_request(
                "Get Order",
                "GET",
                "/v1/orders/{{order_id}}",
                "Get order details (requires orders:view)"
            ),
            create_request(
                "Create Order",
                "POST",
                "/v1/orders",
                "Create a new order (requires orders:edit)",
                {
                    "customer_id": "customer-uuid",
                    "items": [
                        {
                            "product_id": "product-uuid",
                            "quantity": 2,
                            "unit_price": 99.99
                        }
                    ]
                }
            ),
            create_request(
                "Update Order Status",
                "PATCH",
                "/v1/orders/{{order_id}}",
                "Update order status (requires orders:edit)",
                {
                    "status": "processing"
                }
            )
        ]
    }
    collection["item"].append(orders_folder)
    
    # RBAC folder
    rbac_folder = {
        "name": "RBAC",
        "description": "Role-based access control (requires users:manage)",
        "item": [
            create_request(
                "List Permissions",
                "GET",
                "/v1/permissions",
                "List all available permissions"
            ),
            create_request(
                "List Roles",
                "GET",
                "/v1/roles",
                "List tenant roles"
            ),
            create_request(
                "Get Role Details",
                "GET",
                "/v1/roles/{{role_id}}",
                "Get role with permissions"
            ),
            create_request(
                "Create Role",
                "POST",
                "/v1/roles",
                "Create custom role (requires users:manage)",
                {
                    "name": "Custom Role",
                    "description": "Role description"
                }
            ),
            create_request(
                "Add Permissions to Role",
                "POST",
                "/v1/roles/{{role_id}}/permissions",
                "Add permissions to role (requires users:manage)",
                {
                    "permission_codes": ["catalog:view", "orders:view"]
                }
            ),
            create_request(
                "Assign Roles to User",
                "POST",
                "/v1/memberships/{{tenant_id}}/{{user_id}}/roles",
                "Assign roles to user (requires users:manage)",
                {
                    "role_ids": ["role-uuid-1", "role-uuid-2"]
                }
            ),
            create_request(
                "Grant User Permission",
                "POST",
                "/v1/users/{{user_id}}/permissions",
                "Grant permission override (requires users:manage)",
                {
                    "permission_code": "finance:reconcile",
                    "granted": True,
                    "reason": "Temporary access for audit"
                }
            ),
            create_request(
                "List Audit Logs",
                "GET",
                "/v1/audit-logs",
                "View audit trail (requires analytics:view)"
            )
        ]
    }
    collection["item"].append(rbac_folder)
    
    # Settings folder
    settings_folder = {
        "name": "Settings",
        "description": "Tenant settings and integrations",
        "item": [
            create_request(
                "Get Business Settings",
                "GET",
                "/v1/settings/business",
                "Get business settings"
            ),
            create_request(
                "Update Business Settings",
                "PUT",
                "/v1/settings/business",
                "Update business settings (requires users:manage or integrations:manage)",
                {
                    "timezone": "Africa/Nairobi",
                    "business_hours": {
                        "monday": {"open": "09:00", "close": "17:00"}
                    }
                }
            ),
            create_request(
                "List API Keys",
                "GET",
                "/v1/settings/api-keys",
                "List API keys (requires users:manage)"
            ),
            create_request(
                "Generate API Key",
                "POST",
                "/v1/settings/api-keys",
                "Generate new API key (requires users:manage)",
                {
                    "name": "Production Key"
                }
            ),
            create_request(
                "Get Onboarding Status",
                "GET",
                "/v1/settings/onboarding",
                "Get onboarding progress"
            ),
            create_request(
                "Complete Onboarding Step",
                "POST",
                "/v1/settings/onboarding/complete",
                "Mark onboarding step complete",
                {
                    "step": "twilio_configured"
                }
            ),
            create_request(
                "Update Twilio Credentials",
                "PUT",
                "/v1/settings/integrations/twilio",
                "Configure Twilio (requires integrations:manage)",
                {
                    "account_sid": "ACxxxxx",
                    "auth_token": "xxxxx",
                    "whatsapp_number": "+14155238886"
                }
            )
        ]
    }
    collection["item"].append(settings_folder)
    
    # Analytics folder
    analytics_folder = {
        "name": "Analytics",
        "description": "Business analytics (requires analytics:view)",
        "item": [
            create_request(
                "Get Analytics Overview",
                "GET",
                "/v1/analytics",
                "Get analytics overview (requires analytics:view)"
            ),
            create_request(
                "Get Daily Analytics",
                "GET",
                "/v1/analytics/daily",
                "Get daily analytics with date range (requires analytics:view)"
            )
        ]
    }
    collection["item"].append(analytics_folder)
    
    return collection


def generate_environment():
    """Generate Postman environment template."""
    environment = {
        "name": "Tulia AI Development",
        "values": [
            {
                "key": "base_url",
                "value": "http://localhost:8000",
                "type": "default",
                "enabled": True
            },
            {
                "key": "tenant_id",
                "value": "",
                "type": "default",
                "enabled": True
            },
            {
                "key": "tenant_api_key",
                "value": "",
                "type": "secret",
                "enabled": True
            },
            {
                "key": "jwt_token",
                "value": "",
                "type": "secret",
                "enabled": True
            },
            {
                "key": "product_id",
                "value": "",
                "type": "default",
                "enabled": True
            },
            {
                "key": "order_id",
                "value": "",
                "type": "default",
                "enabled": True
            },
            {
                "key": "role_id",
                "value": "",
                "type": "default",
                "enabled": True
            },
            {
                "key": "user_id",
                "value": "",
                "type": "default",
                "enabled": True
            }
        ],
        "_postman_variable_scope": "environment",
        "_postman_exported_at": datetime.now().astimezone().isoformat(),
        "_postman_exported_using": "Tulia AI Collection Generator"
    }
    return environment


def main():
    """Generate and save Postman collection and environment."""
    print("Generating Postman collection...")
    collection = generate_collection()
    
    collection_path = os.path.join(BASE_DIR, "postman_collection.json")
    with open(collection_path, 'w') as f:
        json.dump(collection, f, indent=2)
    print(f"✓ Collection saved to: {collection_path}")
    
    print("\nGenerating Postman environment template...")
    environment = generate_environment()
    
    env_path = os.path.join(BASE_DIR, "postman_environment_template.json")
    with open(env_path, 'w') as f:
        json.dump(environment, f, indent=2)
    print(f"✓ Environment template saved to: {env_path}")
    
    print("\n" + "="*60)
    print("Postman collection generated successfully!")
    print("="*60)
    print("\nNext steps:")
    print("1. Import postman_collection.json into Postman")
    print("2. Import postman_environment_template.json as environment")
    print("3. Fill in environment variables:")
    print("   - tenant_id: Get from /v1/tenants after registration")
    print("   - tenant_api_key: Generate via /v1/settings/api-keys")
    print("   - jwt_token: Get from /v1/auth/login response")
    print("\nAuthentication patterns:")
    print("- Auth endpoints: No headers required")
    print("- Tenant endpoints: X-TENANT-ID + X-TENANT-API-KEY")
    print("- JWT endpoints: Authorization: Bearer {{jwt_token}}")
    print("- Combined: JWT + X-TENANT-ID for tenant-scoped operations")


if __name__ == "__main__":
    main()
