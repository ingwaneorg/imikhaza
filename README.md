# imikhaza - Ticks and Crosses

A Flask-based classroom response system for getting instant feedback from students.

## Features
- ✅ Student reactions (tick, cross, happy, etc.)
- 📊 Multiple choice polling (A, B, C, D, E)
- 📈 Real-time poll results
- 🎯 Room-based sessions

## Quick Start

### Local Development
```bash
pip install -r requirements.txt
python app.py
```
Visit http://localhost:8000

### Deploy to Google Cloud Run
```bash
# Deploy to Google Cloud
./deploy.sh

```

## Project Structure
```
imikhaza/
├── app.py                # Main Flask application
├── requirements.txt      # Python dependencies  
├── Dockerfile            # Container configuration
├── deploy.sh             # Production deployment script
├── deploy-test.sh        # Testing deployment script
├── static/
│   └── app.css           # Your CSS styles
└── templates/
    ├── base.html         # Base template
    ├── intro.html        # Home page
    ├── learner.html      # Student interface
    ├── tutor.html        # Teacher interface
    ├── poll.html         # Poll results
    └── about.html        # About page
```

## Usage

1. **Create a room**: Tutor visits `/` and creates a room code
2. **Join as tutor**: Click "I'm the tutor" to get tutor view with student list
3. **Students join**: Students visit `/ROOMCODE` and enter their name
4. **Get feedback**: Students click reaction buttons, tutor sees responses
5. **View results**: Visit `/ROOMCODE/poll` or counts by status

## Environment Variables

- `FLASK_DEBUG=true` - Show functionailty onlu used in development (like mock data)

## Security Features

- Room codes validated (letters, numbers, hyphens only, 2-10 chars)
- Query parameters blocked for security
- Input length limits enforced
- XSS protection via proper escaping

## Cost Optimization

- No continuous polling (saves Google Cloud costs)
- Tutor page refreshes every 5 seconds only
- Students only send requests when clicking buttons
- Scales to zero when not in use
- Designed to stay within Google Cloud free tier (2M requests/month)

---
