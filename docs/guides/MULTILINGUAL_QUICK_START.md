# Multilingual Bot - Quick Start Guide 🇰🇪

## Overview

The WabotIQ bot now speaks English, Swahili, and Sheng naturally! It understands code-switching and matches the customer's vibe.

## How It Works

### Automatic Language Detection

The bot automatically detects what language(s) the customer is using:

```python
"Niaje buda, una laptop ngapi?"
→ Detected: ['sheng', 'sw']
→ Mix Type: mixed
→ Energy: casual
```

### Smart Response Formatting

The bot matches the customer's language and energy:

```
Customer: "Niaje, una phone ngapi?"
Bot: "Mambo! Poa. We have phones from 5K to 50K. Unataka gani?"

Customer: "Bei gani ya laptop?"
Bot: "Sawa! Laptops start from 25K. Unataka ya gaming ama office work?"

Customer: "Good morning, I need a laptop"
Bot: "Good morning! I'd be happy to help. For office work, I recommend..."
```

## Supported Languages

### English
- Formal and casual
- Professional responses
- Clear and concise

### Swahili
- Standard Kenyan Swahili
- Common phrases and expressions
- Natural greetings and confirmations

### Sheng (Kenyan Slang)
- Street language
- Casual and fun
- Popular expressions

### Code-Switching
- Mix of all three languages
- Natural Kenyan conversation style
- Matches customer's vibe

## Common Phrases

### Greetings
- **Sheng**: Niaje, Mambo, Sasa, Vipi
- **Swahili**: Habari, Hujambo, Shikamoo
- **Mixed**: "Niaje! How can I help?"

### Confirmations
- **Sheng**: Poa, Fiti, Sawa sawa, Bomba
- **Swahili**: Sawa, Nzuri, Ndio
- **Mixed**: "Poa! Got it."

### Thanks
- **Sheng**: Asante buda, Poa msee
- **Swahili**: Asante sana, Karibu sana
- **Mixed**: "Asante! Happy to help!"

### Questions
- **Sheng**: Ni ngapi? Iko? Una nini?
- **Swahili**: Bei gani? Kuna? Unataka nini?
- **Mixed**: "Unataka which one?"

## Energy Levels

The bot detects and matches customer energy:

### Casual
```
Customer: "Niaje msee"
Bot: "Mambo! Vipi buda?"
```

### Formal
```
Customer: "Good morning, could you please help me"
Bot: "Good morning! I'd be happy to assist you."
```

### Excited
```
Customer: "Wow! That's amazing!!!"
Bot: "Fiti kabisa! Right? 🔥"
```

## Configuration

### No Configuration Needed!

The multilingual features work automatically for all tenants. The bot:
- ✅ Detects language automatically
- ✅ Matches customer's vibe
- ✅ Adds personality naturally
- ✅ Code-switches when appropriate

### Optional: Use Qwen Models

For best multilingual performance, use Qwen models via Together AI:

```python
# Tenant settings
tenant.settings.llm_provider = "together"
tenant.settings.llm_model = "Qwen/Qwen2.5-72B-Instruct-Turbo"
```

**Why Qwen?**
- Excellent Swahili support
- Better than OpenAI for African languages
- Natural code-switching
- Cost-effective ($1.20/1M tokens vs OpenAI $15/1M)

## Examples

### Example 1: Shopping for Phone

```
Customer: "Niaje, nataka phone ya bei poa"
Bot: "Mambo! Sawa. For good prices, check out:
1. Tecno Spark 10 - 12K
2. Samsung A14 - 18K
3. Infinix Note 30 - 15K

Unapenda gani?"

Customer: "Number 2"
Bot: "Poa! Samsung A14 - 18K. It has:
- 6.6 inch screen
- 50MP camera
- 5000mAh battery
Fiti? Shall I add it to your cart?"

Customer: "Sawa, add it"
Bot: "Bomba! Added Samsung A14 to your cart. 
Total: 18K
Ready to checkout? Just say 'checkout' ama 'malipo'."
```

### Example 2: Booking Service

```
Customer: "Habari, ningependa kubook appointment ya haircut"
Bot: "Habari! Sawa. Our haircut services:
1. Basic Cut - 500 KES, 30 mins
2. Premium Cut + Styling - 1000 KES, 1 hour
3. Full Grooming Package - 1500 KES, 1.5 hours

Unataka gani?"

Customer: "Premium cut"
Bot: "Nzuri! Premium Cut + Styling (1000 KES, 1 hour).
Available slots leo:
- 2:00 PM
- 4:00 PM
- 6:00 PM

Unapenda saa ngapi?"
```

### Example 3: Mixed Language

```
Customer: "Uko na laptop for gaming?"
Bot: "Yes! We have gaming laptops. Budget yako ni ngapi?"

Customer: "Around 50K"
Bot: "Poa! For 50K, I recommend:
1. HP Pavilion Gaming - 48K
   - Intel i5, 8GB RAM, GTX 1650
   - Perfect for gaming
2. Acer Nitro 5 - 52K
   - Intel i5, 16GB RAM, GTX 1650
   - Slightly better specs

Which one unapenda?"
```

## Testing

### Test Language Detection

```python
from apps.bot.services.multi_language_processor import MultiLanguageProcessor

# Test messages
messages = [
    "Niaje buda, una laptop ngapi?",  # Sheng + Swahili
    "Bei gani ya phone?",              # Swahili
    "Hello, I need help",              # English
]

for msg in messages:
    langs = MultiLanguageProcessor.detect_languages(msg)
    print(f"{msg} → {langs}")
```

### Test Response Formatting

```python
# Original response
response = "Hello! Thank you for your order."

# Format for Sheng customer
formatted = MultiLanguageProcessor.format_response_in_language(
    response, 
    target_language='sheng',
    add_personality=True
)
# Result: "Niaje! Asante buda for your order."
```

## Tips for Best Results

### 1. Let the Bot Match the Customer
Don't force a language - let the bot detect and match naturally.

### 2. Use Qwen for Multilingual
If you have many Swahili/Sheng customers, use Qwen models:
```python
tenant.settings.llm_model = "Qwen/Qwen2.5-72B-Instruct-Turbo"
```

### 3. Monitor Customer Feedback
Track which language mix customers prefer and adjust if needed.

### 4. Test with Real Phrases
Use actual customer messages to test the bot's understanding.

## Troubleshooting

### Bot Not Detecting Language

**Issue**: Bot responds in English only

**Solution**: Check that the customer message contains recognizable Swahili/Sheng phrases. The bot needs at least one phrase to detect the language.

### Bot Too Formal

**Issue**: Bot doesn't use enough Sheng/personality

**Solution**: This is intentional - the bot matches the customer's energy. If the customer is formal, the bot stays formal. If casual, it gets casual.

### Wrong Language Mix

**Issue**: Bot uses wrong language

**Solution**: The bot prioritizes the most frequent language in the message. If a customer uses mostly English with one Swahili word, the bot will respond mostly in English.

## FAQ

**Q: Does this work for all tenants?**  
A: Yes! Multilingual features are enabled for all tenants automatically.

**Q: Can I disable personality features?**  
A: Yes, set `add_personality=False` in the response formatter.

**Q: Which LLM model is best for multilingual?**  
A: Qwen 2.5 72B has the best Swahili support. GPT-4o is also good but more expensive.

**Q: Does this work with voice messages?**  
A: Yes, if you transcribe the voice to text first.

**Q: Can I add more languages?**  
A: Yes! Add phrases to `SWAHILI_PHRASES` or `SHENG_PHRASES` in `multi_language_processor.py`.

**Q: How accurate is language detection?**  
A: Very accurate for messages with 2+ recognizable phrases. May default to English for very short messages.

## Support

For issues or questions:
1. Check the main documentation: `MULTILINGUAL_TOGETHER_AI_LEGACY_CLEANUP.md`
2. Review the code: `apps/bot/services/multi_language_processor.py`
3. Test with: `python manage.py shell` and import the processor

---

**Karibu! Enjoy the multilingual bot! 🇰🇪🎉**
