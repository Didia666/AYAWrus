# CyberLearn Assistant - Educational Cybersecurity Chatbot

## Overview

CyberLearn Assistant is a modern, searchable educational chatbot integrated into the Malware Detection System. It provides intelligent access to a comprehensive local knowledge base of 32+ curated cybersecurity topics covering malware types, machine learning detection, scan analysis, and prevention strategies.

## Key Features

✅ **No External APIs** - Fully local knowledge base, zero external dependencies
✅ **Intelligent Search** - Keyword matching algorithm finds relevant topics instantly  
✅ **Chat Interface** - Modern chat bubbles with timestamps and typing animations
✅ **Related Topics** - Automatically suggests follow-up questions for deeper learning
✅ **Responsive Design** - Works on desktop with adaptive UI
✅ **Easy to Extend** - Add new topics by editing JSON knowledge base only
✅ **Dual UI Support** - Both PyQt6 and DearPyGui implementations
✅ **Professional UI** - Modern gradient buttons, smooth animations, clean layout

## Architecture

### Knowledge Base Structure

**File**: `cyberlearn_knowledge_base.json`

Organized into 4 categories:

1. **Malware** (🦠) - 8 topics
   - Trojans, viruses, worms, spyware, backdoors, rootkits, adware, malware indicators, polymorphic malware

2. **Machine Learning** (🤖) - 8 topics
   - Random Forest, ML features, confidence scores, false positives, accuracy metrics, deep learning, signatures, heuristics

3. **Scan Results** (📊) - 6 topics
   - PE entropy, file analysis, threat severity, quarantine benefits, scan types, real-time protection

4. **Cybersecurity Prevention** (🔒) - 10 topics
   - Backup strategies, patch management, strong passwords, MFA, phishing awareness, firewalls, user training, system hardening, incident response

### Knowledge Base Format

Each topic has:
- **id**: Unique identifier for linking
- **question**: User-facing question text
- **answer**: Comprehensive answer (500+ words)
- **keywords**: List of search keywords
- **related**: Array of related topic IDs for follow-up suggestions

```json
{
  "id": "trojan_virus_diff",
  "question": "What is a Trojan and how does it differ from a virus?",
  "answer": "A Trojan is malware disguised as...",
  "keywords": ["trojan", "virus", "malware", "difference"],
  "related": ["ransomware", "worm", "backdoor"]
}
```

### Components

#### PyQt6 Version (`views/cyberlearn_assistant.py`)

- **KnowledgeBase** - Loads and searches knowledge base
- **TypingSimulator** - QThread for animated text display
- **MessageBubble** - Custom widget for styled chat messages
- **CyberLearnWindow** - Main chat interface with search and suggestions
- **FloatingButton** - Always-on-top floating button
- Integration functions: `initialize_cyberlearn()`, `show_cyberlearn_widget()`

#### DearPyGui Version (`views/cyberlearn_assistant_dpg.py`)

- Same KnowledgeBase class
- DPG-native widgets for window management
- Threading-safe message handling
- Integration function: `init_cyberlearn_for_dpg()`

## Usage

### Starting PyQt6 Version

```bash
python main.py
```

Look for the 🎓 button in the bottom-right corner.

### Starting DearPyGui Version

```bash
python main_dpg.py
```

The 🎓 floating button appears independently.

## User Interface

### Main Features

1. **Floating Button** (🎓)
   - Always visible in bottom-right corner
   - Gradient blue background with hover effects
   - Single click opens chat window

2. **Search Bar**
   - Type keywords to search knowledge base
   - Examples: "Trojan", "Random Forest", "entropy", "ransomware"
   - Press Enter or click Search

3. **Suggested Topics**
   - 6 popular topics displayed as suggestion buttons
   - Click any topic for instant answer
   - Suggestions update based on relevance

4. **Chat Display**
   - User messages (blue bubble)
   - Assistant responses (light gray bubble)
   - System messages (light blue, informational)
   - Timestamps on all messages
   - Auto-scrolling to latest messages

5. **Typing Animation**
   - 0.6 second thinking delay before response
   - Character-by-character animation (20ms per char)
   - Creates natural, engaging interaction

6. **Related Topics**
   - After each answer, related questions appear
   - Encourages deeper learning on connected topics
   - Related topics determined by topic metadata

## Adding New Topics

### Step 1: Edit Knowledge Base

Open `cyberlearn_knowledge_base.json` and add to appropriate category:

```json
{
  "id": "new_topic_id",
  "question": "Your question here?",
  "answer": "Comprehensive answer (aim for 300+ words)...",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "related": ["existing_topic_id1", "existing_topic_id2"]
}
```

### Step 2: Link to Related Topics

Update existing topics to reference your new topic:

```json
{
  "id": "existing_topic",
  "related": ["new_topic_id", "other_topic"]
}
```

### Step 3: Restart Application

New topics automatically appear in search and suggestions.

## Search Algorithm

The search uses a 3-tier matching system:

1. **Primary Match (Score: 100)** - Question text match
2. **Secondary Match (Score: 80)** - Keywords match
3. **Tertiary Match (Score: 60)** - Answer content match

Results sorted by score, duplicates removed, top 5 returned.

## Customization

### Typing Speed

In `views/cyberlearn_assistant.py`, modify `TypingSimulator` initialization:

```python
# Slower: 30ms per character
self._typing_thread = TypingSimulator(topic["answer"], delay_ms=30)

# Faster: 10ms per character
self._typing_thread = TypingSimulator(topic["answer"], delay_ms=10)
```

### UI Colors

Edit stylesheet strings in PyQt6 version:
- Blue gradient: `#2c7be5` → `#1b6fd8`
- Message bubbles: Modify QFrame and QTextEdit styles
- Buttons: Update QPushButton stylesheet

### Categories

Modify or add categories in knowledge base metadata section.

## Performance

- **Memory**: ~5-8MB for entire module with knowledge base
- **Startup**: <200ms additional to app startup
- **Search**: <10ms for typical query
- **Response Display**: Instant (no network calls)

## File Structure

```
Malware-Detection-System/
├── cyberlearn_knowledge_base.json    # 32+ topics, 4 categories
├── main.py                           # PyQt6 entry point (includes CyberLearn)
├── main_dpg.py                       # DearPyGui entry point (includes CyberLearn)
├── views/
│   ├── cyberlearn_assistant.py       # PyQt6 implementation
│   ├── cyberlearn_assistant_dpg.py   # DearPyGui implementation
│   └── ...
└── ...
```

## Technical Details

### Threading Model

- Main UI thread remains responsive
- Search operations execute on main thread (<10ms)
- Typing animation runs in separate QThread
- DPG version uses daemon threads for searches

### Error Handling

- Missing knowledge base: Loads with empty topics
- Invalid JSON: Gracefully skipped
- Missing related topics: Silently ignored
- File access errors: Logged to console

### Compatibility

- **Python**: 3.8+
- **PyQt6**: 6.0+
- **DearPyGui**: 1.6+
- **OS**: Windows, macOS, Linux

## Future Enhancements

Potential improvements without external APIs:

- [ ] Conversation history export
- [ ] User ratings on answers
- [ ] Category filtering
- [ ] Full-text search with stemming
- [ ] Offline knowledge base updates
- [ ] Discussion forum integration
- [ ] Learning progress tracking
- [ ] Dark mode toggle

## Troubleshooting

### Chatbot doesn't appear

- Ensure `cyberlearn_knowledge_base.json` exists in app root
- Check console for error messages
- Restart application

### Search returns no results

- Try simpler keywords
- Check knowledge base is valid JSON
- Verify keywords in topic definitions

### UI looks broken

- Check PyQt6/DearPyGui versions
- Verify screen resolution (test on 1024x768+)
- Look for stylesheet errors in console

## Performance Tips

- Keep knowledge base <50 topics (currently 32)
- Use concise keywords (3-5 per topic)
- Keep answers to 500-1000 words
- Related topics: 3-5 per topic

## Support

For issues, check:
1. Knowledge base JSON validity
2. File paths and permissions
3. Python dependencies installed
4. Screen resolution and DPI settings

## License

Same as Malware Detection System project.
