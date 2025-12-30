"""
Authentication REST API views.

Implements endpoints for:
- User registration
- Login
- Email verification
- Password reset
- User profile management
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.mail import send_mail
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.rbac.models import User
from apps.rbac.services import AuthService
from apps.rbac.serializers import (
    RegistrationSerializer, LoginSerializer, EmailVerificationSerializer,
    PasswordResetRequestSerializer, PasswordResetSerializer,
    UserProfileSerializer, UserProfileUpdateSerializer
)


@extend_schema(
    tags=['Authentication'],
    summary='Register new user',
    description='''
Register a new user account with first tenant.

Creates:
- User account with hashed password
- First tenant (trial status)
- TenantUser membership with Owner role
- TenantSettings with defaults
- Email verification token

Returns JWT token for immediate login and tenant information.

**No authentication required** - this is a public endpoint.

**Rate limit**: 3 requests/hour per IP
    ''',
    request=RegistrationSerializer,
    responses={
        201: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Registration Request',
            value={
                'email': 'user@example.com',
                'password': 'SecurePass123!',
                'first_name': 'John',
                'last_name': 'Doe',
                'business_name': 'Acme Corp'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'user': {
                    'id': '123e4567-e89b-12d3-a456-426614174000',
                    'email': 'user@example.com',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'full_name': 'John Doe',
                    'email_verified': False
                },
                'tenant': {
                    'id': '123e4567-e89b-12d3-a456-426614174001',
                    'name': 'Acme Corp',
                    'slug': 'acme-corp',
                    'status': 'active'
                },
                'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'message': 'Registration successful. Please check your email to verify your account.'
            },
            response_only=True
        ),
        OpenApiExample(
            'Email Already Exists',
            value={
                'error': 'Validation error',
                'details': {
                    'email': ['A user with this email already exists.']
                }
            },
            response_only=True,
            status_codes=['400']
        ),
        OpenApiExample(
            'Rate Limit Exceeded',
            value={
                'error': 'Rate limit exceeded. Please try again later.'
            },
            response_only=True,
            status_codes=['429']
        )
    ]
)
@method_decorator(ratelimit(key='ip', rate='3/h', method='POST', block=False), name='dispatch')
class RegistrationView(APIView):
    """
    POST /v1/auth/register
    
    Register new user with first tenant.
    
    No authentication required.
    Rate limited to 3 requests per hour per IP.
    """
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """Register new user."""
        from apps.core.logging import SecurityLogger
        
        # Check if rate limited
        if getattr(request, 'limited', False):
            # Get client IP
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            
            # Log rate limit violation
            SecurityLogger.log_rate_limit_exceeded(
                endpoint='/v1/auth/register',
                ip_address=ip_address,
                limit='3/hour per IP'
            )
            
            retry_after = 3600  # 1 hour
            response = Response(
                {
                    'error': 'Rate limit exceeded. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'retry_after': retry_after
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
            response['Retry-After'] = str(retry_after)
            return response
        
        serializer = RegistrationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Validation error',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Register user
            result = AuthService.register_user(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                business_name=serializer.validated_data['business_name'],
                first_name=serializer.validated_data['first_name'],
                last_name=serializer.validated_data['last_name']
            )
            
            user = result['user']
            tenant = result['tenant']
            token = result['token']
            verification_token = result['verification_token']
            
            # Send verification email
            verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
            
            # Use our enhanced email service
            from apps.core.services.email_service import send_welcome_email
            
            try:
                email_sent = send_welcome_email(
                    user_email=user.email,
                    user_name=user.get_full_name(),
                    verification_url=verification_url
                )
                
                if not email_sent:
                    logger.warning(f"Failed to send welcome email to {user.email}")
                    
            except Exception as e:
                # Log error but don't fail registration
                logger.error(f"Failed to send welcome email to {user.email}: {e}")
            
            # Return response
            return Response(
                {
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'full_name': user.get_full_name(),
                        'email_verified': user.email_verified,
                    },
                    'tenant': {
                        'id': str(tenant.id),
                        'name': tenant.name,
                        'slug': tenant.slug,
                        'status': tenant.status,
                    },
                    'token': token,
                    'message': 'Registration successful. Please check your email to verify your account.'
                },
                status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            return Response(
                {
                    'error': str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Registration failed")
            
            return Response(
                {
                    'error': 'Registration failed. Please try again.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Authentication'],
    summary='Login user',
    description='''
Authenticate user with email and password.

Returns JWT token for API authentication and user information.

**No authentication required** - this is a public endpoint.

**Rate limits**:
- 5 requests/minute per IP address
- 10 requests/hour per email address
    ''',
    request=LoginSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        401: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Login Request',
            value={
                'email': 'user@example.com',
                'password': 'SecurePass123!'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'user': {
                    'id': '123e4567-e89b-12d3-a456-426614174000',
                    'email': 'user@example.com',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'full_name': 'John Doe',
                    'email_verified': True
                },
                'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'message': 'Login successful'
            },
            response_only=True
        ),
        OpenApiExample(
            'Invalid Credentials',
            value={
                'error': 'Invalid email or password'
            },
            response_only=True,
            status_codes=['401']
        ),
        OpenApiExample(
            'Rate Limit Exceeded',
            value={
                'error': 'Rate limit exceeded. Please try again later.',
                'code': 'RATE_LIMIT_EXCEEDED'
            },
            response_only=True,
            status_codes=['429']
        )
    ]
)
@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=False), name='dispatch')
@method_decorator(ratelimit(key='post:email', rate='10/h', method='POST', block=False), name='dispatch')
class LoginView(APIView):
    """
    POST /v1/auth/login
    
    Authenticate user and return JWT token.
    
    No authentication required.
    Rate limited to:
    - 5 requests per minute per IP address
    - 10 requests per hour per email address
    """
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """Login user."""
        from apps.core.logging import SecurityLogger
        
        # Check if rate limited
        if getattr(request, 'limited', False):
            # Get client IP and email
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            email = request.data.get('email', 'unknown') if hasattr(request, 'data') else 'unknown'
            
            # Log rate limit violation
            SecurityLogger.log_rate_limit_exceeded(
                endpoint='/v1/auth/login',
                ip_address=ip_address,
                user_email=email,
                limit='5/min per IP or 10/hour per email'
            )
            
            retry_after = 60  # 1 minute
            response = Response(
                {
                    'error': 'Rate limit exceeded. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'retry_after': retry_after
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
            response['Retry-After'] = str(retry_after)
            return response
        
        serializer = LoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Validation error',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Attempt login
        result = AuthService.login(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        
        if not result:
            # Log failed login attempt
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            
            SecurityLogger.log_failed_login(
                email=serializer.validated_data['email'],
                ip_address=ip_address,
                user_agent=user_agent,
                reason='Invalid credentials'
            )
            
            return Response(
                {
                    'error': 'Invalid email or password'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        user = result['user']
        token = result['token']
        
        return Response(
            {
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'full_name': user.get_full_name(),
                    'email_verified': user.email_verified,
                },
                'token': token,
                'message': 'Login successful'
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Authentication'],
    summary='Verify email address',
    description='''
Verify user email address with verification token.

Token is sent via email during registration and is valid for 24 hours.

**No authentication required** - this is a public endpoint.

**Rate limit**: 10 requests/hour per IP
    ''',
    request=EmailVerificationSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Verification Request',
            value={
                'token': 'abc123def456...'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Email verified successfully'
            },
            response_only=True
        ),
        OpenApiExample(
            'Invalid Token',
            value={
                'error': 'Invalid or expired verification token'
            },
            response_only=True,
            status_codes=['400']
        ),
        OpenApiExample(
            'Rate Limit Exceeded',
            value={
                'error': 'Rate limit exceeded. Please try again later.',
                'code': 'RATE_LIMIT_EXCEEDED'
            },
            response_only=True,
            status_codes=['429']
        )
    ]
)
@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=False), name='dispatch')
class EmailVerificationView(APIView):
    """
    POST /v1/auth/verify-email
    
    Verify user email with token.
    
    No authentication required.
    Rate limited to 10 requests per hour per IP.
    """
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """Verify email."""
        from apps.core.logging import SecurityLogger
        
        # Check if rate limited
        if getattr(request, 'limited', False):
            # Get client IP
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            
            # Log rate limit violation
            SecurityLogger.log_rate_limit_exceeded(
                endpoint='/v1/auth/verify-email',
                ip_address=ip_address,
                limit='10/hour per IP'
            )
            
            retry_after = 3600  # 1 hour
            response = Response(
                {
                    'error': 'Rate limit exceeded. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'retry_after': retry_after
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
            response['Retry-After'] = str(retry_after)
            return response
        
        serializer = EmailVerificationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Validation error',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify email
        success = AuthService.verify_email(
            token=serializer.validated_data['token']
        )
        
        if not success:
            return Response(
                {
                    'error': 'Invalid or expired verification token'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {
                'message': 'Email verified successfully'
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Authentication'],
    summary='Request password reset',
    description='''
Request password reset for a user account.

Sends password reset email with token valid for 24 hours.

**No authentication required** - this is a public endpoint.

**Rate limit**: 3 requests/hour per IP
    ''',
    request=PasswordResetRequestSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Password Reset Request',
            value={
                'email': 'user@example.com'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'If an account exists with this email, a password reset link has been sent.'
            },
            response_only=True
        ),
        OpenApiExample(
            'Rate Limit Exceeded',
            value={
                'error': 'Rate limit exceeded. Please try again later.'
            },
            response_only=True,
            status_codes=['429']
        )
    ]
)
@method_decorator(ratelimit(key='ip', rate='3/h', method='POST', block=False), name='dispatch')
class ForgotPasswordView(APIView):
    """
    POST /v1/auth/forgot-password
    
    Request password reset.
    
    No authentication required.
    Rate limited to 3 requests per hour per IP.
    """
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """Request password reset."""
        from apps.core.logging import SecurityLogger
        
        # Check if rate limited
        if getattr(request, 'limited', False):
            # Get client IP
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            
            # Log rate limit violation
            SecurityLogger.log_rate_limit_exceeded(
                endpoint='/v1/auth/forgot-password',
                ip_address=ip_address,
                limit='3/hour per IP'
            )
            
            retry_after = 3600  # 1 hour
            response = Response(
                {
                    'error': 'Rate limit exceeded. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'retry_after': retry_after
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
            response['Retry-After'] = str(retry_after)
            return response
        
        serializer = PasswordResetRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Validation error',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Request password reset
        reset_token = AuthService.request_password_reset(
            email=serializer.validated_data['email']
        )
        
        # Always return success to prevent email enumeration
        if reset_token:
            # Send reset email
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
            try:
                send_mail(
                    subject='Reset your password',
                    message=f'''
You requested to reset your password for your Tulia AI account.

Click the link below to reset your password:

{reset_url}

This link will expire in 24 hours.

If you didn't request this, please ignore this email.

Best regards,
The Tulia AI Team
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[serializer.validated_data['email']],
                    fail_silently=True,
                )
            except Exception as e:
                # Log error but don't fail request
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send password reset email: {e}")
        
        return Response(
            {
                'message': 'If an account exists with this email, a password reset link has been sent.'
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Authentication'],
    summary='Reset password',
    description='''
Reset user password with reset token.

Token is sent via email and is valid for 24 hours.

**No authentication required** - this is a public endpoint.

**Rate limit**: 5 requests/hour per IP
    ''',
    request=PasswordResetSerializer,
    responses={
        200: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        429: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Password Reset Request',
            value={
                'token': 'abc123def456...',
                'new_password': 'NewSecurePass123!'
            },
            request_only=True
        ),
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Password reset successfully'
            },
            response_only=True
        ),
        OpenApiExample(
            'Invalid Token',
            value={
                'error': 'Invalid or expired reset token'
            },
            response_only=True,
            status_codes=['400']
        ),
        OpenApiExample(
            'Rate Limit Exceeded',
            value={
                'error': 'Rate limit exceeded. Please try again later.',
                'code': 'RATE_LIMIT_EXCEEDED'
            },
            response_only=True,
            status_codes=['429']
        )
    ]
)
@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=False), name='dispatch')
class ResetPasswordView(APIView):
    """
    POST /v1/auth/reset-password
    
    Reset password with token.
    
    No authentication required.
    Rate limited to 5 requests per hour per IP.
    """
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """Reset password."""
        from apps.core.logging import SecurityLogger
        
        # Check if rate limited
        if getattr(request, 'limited', False):
            # Get client IP
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            
            # Log rate limit violation
            SecurityLogger.log_rate_limit_exceeded(
                endpoint='/v1/auth/reset-password',
                ip_address=ip_address,
                limit='5/hour per IP'
            )
            
            retry_after = 3600  # 1 hour
            response = Response(
                {
                    'error': 'Rate limit exceeded. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'retry_after': retry_after
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
            response['Retry-After'] = str(retry_after)
            return response
        
        serializer = PasswordResetSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Validation error',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset password
        success = AuthService.reset_password(
            token=serializer.validated_data['token'],
            new_password=serializer.validated_data['new_password']
        )
        
        if not success:
            return Response(
                {
                    'error': 'Invalid or expired reset token'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {
                'message': 'Password reset successfully'
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Authentication'],
    summary='Logout user',
    description='''
Logout the authenticated user.

Since JWT tokens are stateless, this endpoint primarily serves as a client-side signal
to clear the token. The token will remain valid until expiration.

For enhanced security, consider implementing a token blacklist if needed.

Requires valid JWT token in Authorization header.
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        401: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Success Response',
            value={
                'message': 'Logout successful'
            },
            response_only=True
        )
    ]
)
class LogoutView(APIView):
    """
    POST /v1/auth/logout
    
    Logout user (client-side token clearing).
    
    Requires JWT authentication.
    """
    
    def post(self, request):
        """Logout user."""
        # User is attached to request by authentication middleware
        user = request.user
        
        if not user or not hasattr(user, 'id'):
            return Response(
                {
                    'error': 'Authentication required'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Since JWT is stateless, logout is handled client-side
        # This endpoint serves as a confirmation
        return Response(
            {
                'message': 'Logout successful'
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Authentication'],
    summary='Refresh JWT token',
    description='''
Refresh JWT token for authenticated user.

Returns a new JWT token with extended expiration.

Requires valid JWT token in Authorization header.
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        401: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Success Response',
            value={
                'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'message': 'Token refreshed successfully'
            },
            response_only=True
        )
    ]
)
class RefreshTokenView(APIView):
    """
    POST /v1/auth/refresh-token
    
    Refresh JWT token.
    
    Requires JWT authentication.
    """
    
    def post(self, request):
        """Refresh token."""
        # User is attached to request by authentication middleware
        user = request.user
        
        if not user or not hasattr(user, 'id'):
            return Response(
                {
                    'error': 'Authentication required'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Generate new token
        token = AuthService.generate_jwt(user)
        
        return Response(
            {
                'token': token,
                'message': 'Token refreshed successfully'
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Authentication'],
    summary='Get current user profile',
    description='''
Get comprehensive profile information for the authenticated user.

Returns complete user data including:
- Basic profile information (name, email, phone)
- Account status (active, verified, 2FA enabled)
- All tenant memberships with roles and permissions
- Pending tenant invitations
- Activity timestamps

This endpoint is useful for:
- Displaying user profile in the UI
- Building tenant switcher (workspace selector)
- Checking user permissions across tenants
- Managing pending invitations

Requires valid JWT token in Authorization header.
    ''',
    responses={
        200: UserProfileSerializer,
        401: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            'Success Response',
            value={
                'id': '123e4567-e89b-12d3-a456-426614174000',
                'email': 'user@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'full_name': 'John Doe',
                'phone': '+1234567890',
                'is_active': True,
                'is_superuser': False,
                'email_verified': True,
                'two_factor_enabled': False,
                'last_login_at': '2025-01-15T10:30:00Z',
                'created_at': '2025-01-01T00:00:00Z',
                'updated_at': '2025-01-15T10:30:00Z',
                'total_tenants': 2,
                'tenants': [
                    {
                        'membership_id': '456e4567-e89b-12d3-a456-426614174001',
                        'tenant': {
                            'id': '789e4567-e89b-12d3-a456-426614174002',
                            'name': 'Acme Corp',
                            'slug': 'acme-corp',
                            'status': 'active',
                            'subscription': {
                                'tier': 'professional',
                                'status': 'active',
                                'trial_ends_at': None
                            }
                        },
                        'roles': [
                            {
                                'id': 'abc12345-e89b-12d3-a456-426614174003',
                                'name': 'Owner',
                                'description': 'Full access to all features',
                                'is_system': True
                            }
                        ],
                        'scopes': [
                            'analytics:view',
                            'catalog:edit',
                            'catalog:view',
                            'conversations:view',
                            'finance:view',
                            'integrations:manage',
                            'orders:edit',
                            'orders:view',
                            'users:manage'
                        ],
                        'joined_at': '2025-01-01T00:00:00Z',
                        'last_seen_at': '2025-01-15T10:30:00Z'
                    },
                    {
                        'membership_id': '456e4567-e89b-12d3-a456-426614174004',
                        'tenant': {
                            'id': '789e4567-e89b-12d3-a456-426614174005',
                            'name': 'Beta Inc',
                            'slug': 'beta-inc',
                            'status': 'active',
                            'subscription': {
                                'tier': 'trial',
                                'status': 'active',
                                'trial_ends_at': '2025-02-01T00:00:00Z'
                            }
                        },
                        'roles': [
                            {
                                'id': 'def12345-e89b-12d3-a456-426614174006',
                                'name': 'Catalog Manager',
                                'description': 'Manage products and services',
                                'is_system': True
                            }
                        ],
                        'scopes': [
                            'analytics:view',
                            'catalog:edit',
                            'catalog:view',
                            'services:edit',
                            'services:view'
                        ],
                        'joined_at': '2025-01-10T00:00:00Z',
                        'last_seen_at': '2025-01-14T15:20:00Z'
                    }
                ],
                'pending_invites': [
                    {
                        'id': 'ghi12345-e89b-12d3-a456-426614174007',
                        'tenant': {
                            'id': 'jkl12345-e89b-12d3-a456-426614174008',
                            'name': 'Gamma LLC',
                            'slug': 'gamma-llc'
                        },
                        'invited_by': {
                            'email': 'admin@gamma-llc.com',
                            'name': 'Jane Admin'
                        },
                        'invited_at': '2025-01-14T12:00:00Z'
                    }
                ]
            },
            response_only=True
        )
    ]
)
class UserProfileView(APIView):
    """
    GET /v1/auth/me
    PUT /v1/auth/me
    
    Get or update current user profile.
    
    Requires JWT authentication.
    """
    # No permission_classes - authentication handled by middleware
    
    def get(self, request):
        """Get user profile."""
        from django.contrib.auth.models import AnonymousUser
        
        # User is attached to request by authentication middleware
        user = request.user
        
        if not user or isinstance(user, AnonymousUser) or not hasattr(user, 'id'):
            return Response(
                {
                    'error': 'Authentication required',
                    'detail': 'This endpoint requires JWT authentication. Use Authorization: Bearer <token> header.'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request):
        """Update user profile."""
        from django.contrib.auth.models import AnonymousUser
        
        # User is attached to request by authentication middleware
        user = request.user
        
        if not user or isinstance(user, AnonymousUser) or not hasattr(user, 'id'):
            return Response(
                {
                    'error': 'Authentication required'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = UserProfileUpdateSerializer(
            user,
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Validation error',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        
        # Return full profile
        profile_serializer = UserProfileSerializer(user)
        return Response(profile_serializer.data, status=status.HTTP_200_OK)



