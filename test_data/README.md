# WabotIQ Test Data

This directory contains comprehensive test data for WabotIQ, designed to test all aspects of the AI-powered customer service system across different industries.

## 🏢 Business Types Included

### Food & Beverage (5 businesses)
1. **Mama Njeri's Kitchen** - Traditional Kenyan home cooking
2. **Java House Westlands** - Premium coffee house franchise  
3. **Urban Eats Restaurant** - Contemporary fusion cuisine
4. **Spice Route Indian** - Authentic Indian restaurant

### Beauty & Personal Care (2 businesses)
1. **Glamour Salon & Spa** - Full-service salon with nail services
2. **King's Barber Shop** - Traditional and modern barbering

### Retail & E-commerce (1 business)
1. **Scent Safari Perfumes** - Premium fragrance e-commerce

### Healthcare (1 business)
1. **HealthPlus Pharmacy** - Neighborhood pharmacy with health services

### Bookshop (1 business)
1. **Word Alive Christian Bookshop** - Christian books and resources

## 📋 Subscription Tiers

Each business is assigned different subscription tiers to test feature limitations:

### Starter ($29/month, $261/year - 10% discount)
- 1,000 messages/month
- 100 products max
- 5 services max
- No payment processing
- Read-only API access

### Growth ($99/month, $891/year - 10% discount)  
- 5,000 messages/month
- 1,000 products max
- 50 services max
- Payment processing (3.5% fee)
- Full API access
- Custom branding

### Enterprise ($299/month, $2,691/year - 10% discount)
- Unlimited everything
- Payment processing (2.5% fee)
- Priority support
- Full API access
- Custom branding

## 🧪 Testing Scenarios

### 1. Product Catalog Testing
- **In-stock items**: Test normal ordering flow
- **Out-of-stock items**: Test inventory management
- **Product variants**: Test size/color/flavor options
- **Categories**: Test product browsing and filtering

### 2. Service Booking Testing
- **Available services**: Test appointment booking
- **Scheduling conflicts**: Test availability management
- **Service packages**: Test bundled services
- **Cancellations**: Test booking modifications

### 3. Bot Hallucination Testing
- Ask about products not in the catalog
- Request services not offered by the business
- Ask about policies not documented
- Request information outside business scope

### 4. Multi-language Testing
- English conversations (all businesses)
- Swahili conversations (Mama Njeri's, HealthPlus, Word Alive)
- Sheng conversations (King's Barber Shop)

### 5. Industry-specific Testing
- **Food**: Dietary restrictions, delivery times, ingredients
- **Beauty**: Appointment scheduling, service duration, product recommendations
- **Pharmacy**: Prescription requirements, health consultations, insurance
- **E-commerce**: Product authenticity, shipping, returns
- **Bookshop**: Special orders, bulk discounts, religious content

## 🚀 Quick Setup

```bash
# Create subscription tiers and load all test data
python manage.py setup_demo_data

# Or step by step:
python manage.py create_subscription_tiers
python manage.py load_test_tenants

# View subscription information
python manage.py show_subscription_info
```

## 📱 Test WhatsApp Numbers

Each business has a unique WhatsApp number for testing:

- `+254722100001` - Mama Njeri's Kitchen
- `+254722100002` - Java House Westlands  
- `+254722100003` - Word Alive Bookshop
- `+254722100004` - HealthPlus Pharmacy
- `+254722100005` - Scent Safari Perfumes
- `+254722100006` - Glamour Salon & Spa
- `+254722100007` - King's Barber Shop
- `+254722100008` - Urban Eats Restaurant
- `+254722100009` - Spice Route Indian

## 📄 Document Types Included

Each business includes comprehensive documentation:

### Business Documents
- **About**: Company history and mission
- **Return Policy**: Product/service return rules
- **Delivery Policy**: Shipping and delivery information  
- **Payment Policy**: Accepted payment methods and terms

### FAQs
- Industry-specific frequently asked questions
- Common customer concerns and responses
- Policy clarifications and edge cases

## 🎯 Testing Objectives

### Functional Testing
- ✅ Product catalog browsing and search
- ✅ Service booking and scheduling
- ✅ Order placement and tracking
- ✅ Payment processing (Growth/Enterprise tiers)
- ✅ Customer support and handoff

### AI/Bot Testing  
- ✅ Natural language understanding
- ✅ Context retention across conversations
- ✅ Appropriate responses to out-of-scope queries
- ✅ Hallucination detection and prevention
- ✅ Multi-language support

### Business Logic Testing
- ✅ Subscription tier feature limitations
- ✅ Tenant data isolation
- ✅ RBAC permission enforcement
- ✅ Integration with external services

### Performance Testing
- ✅ Multiple concurrent conversations
- ✅ Large product catalogs
- ✅ Complex service scheduling
- ✅ High-volume message processing

## 🔧 Customization

To add your own test business:

1. Create a JSON file in the appropriate category folder
2. Follow the existing schema (see any `.json` file as example)
3. Run `python manage.py load_test_tenants --tenant your-business-slug`

## 📊 Analytics & Reporting

The test data enables testing of:
- Customer conversation analytics
- Product performance metrics  
- Service booking patterns
- Revenue tracking by subscription tier
- Bot performance and accuracy metrics

## 🛡️ Security Testing

Test data includes scenarios for:
- Cross-tenant data isolation
- RBAC permission boundaries
- API key authentication
- Sensitive data handling (pharmacy prescriptions, payment info)

---

This comprehensive test data set ensures thorough testing of all WabotIQ features across diverse business scenarios, helping identify edge cases and validate the AI agent's performance in real-world conditions.