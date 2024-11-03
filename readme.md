# Ummælagreining (Blog Comment Annotation Tool)

A web application for annotating Icelandic blog comments to help improve AI understanding of Icelandic language and culture. This project is a collaboration between the University of Iceland, Reykjavik University, and Miðeind.

## Overview

The application allows users to annotate blog comments across multiple dimensions including:
- Sentiment analysis
- Toxicity detection
- Politeness
- Hate speech detection
- Social acceptability in various contexts
- Emotion detection
- And more

## Technology Stack

- **Backend**: Flask
- **Frontend**: HTML with TailwindCSS and DaisyUI
- **Database**: 
  - Development: SQLite
  - Production: PostgreSQL (Heroku)
- **Authentication**: Flask-Login
- **Email**: Flask-Mail
- **CSS Processing**: PostCSS
- **Security**: Flask-Talisman

## Prerequisites

- Python 3.8+
- Node.js and npm (for TailwindCSS processing)
- PostgreSQL (for production)

## Installation

1. Clone the repository:
```
git clone git@github.com:icelandic-lt/annotation_if_sentiment.git
cd annotation_if_sentiment
```

2. Create and activate a virtual environment:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```
pip install -r app/requirements.txt
```

4. Install Node.js dependencies and build CSS:
```
cd app
npm install
npm run build
```

5. Create a `.env` file in the app directory with the following variables:
```
SECRET_KEY=your-secret-key
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-email-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
DATABASE_URL=sqlite:///app.db  # For development
```

## Development Setup

1. Initialize the database:
```
flask db init
flask db migrate
flask db upgrade
```

2. Run the development server:
```
flask run
```

The application will be available at `http://localhost:5000`

## Production Deployment

The application is configured for deployment on Heroku:

1. Create a new Heroku application
2. Add PostgreSQL addon
3. Configure environment variables in Heroku dashboard
4. Deploy using Git:
```
git push heroku main
```

## Project Structure

```
app/
├── static/          # Static files (CSS, images)
├── templates/       # HTML templates
├── app.py          # Main application file
├── requirements.txt # Python dependencies
├── tailwind.config.js  # TailwindCSS configuration
├── postcss.config.js   # PostCSS configuration
└── terms_and_conditions.py  # Terms and conditions text
```

## Features

- User registration and authentication
- Email verification
- Multiple annotation tasks
- Progress tracking
- Leaderboard
- Feedback system comparing user annotations with AI predictions
- Mobile-responsive design
- Issue reporting system
- Progress sharing functionality

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Security

The application implements several security measures:
- HTTPS enforcement in production
- Content Security Policy
- Secure password hashing
- CSRF protection
- Email verification
- Secure session handling

## License

This project is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0). This means you are free to:

- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform, and build upon the material for any purpose, even commercially

Under the following terms:
- Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made.

For more details, see https://creativecommons.org/licenses/by/4.0/

## Contact

For questions or issues, please contact:
- Hafsteinn Einarsson (hafsteinne@hi.is)
- Steinunn Rut Friðriksdóttir (srf2@hi.is)

## Acknowledgments

This project is a collaboration between:
- University of Iceland
- Reykjavik University
- Miðeind

The project aims to create a dataset that reflects Icelandic values and culture, particularly in areas such as inappropriate or offensive discourse, to improve AI understanding of Icelandic language and cultural context.