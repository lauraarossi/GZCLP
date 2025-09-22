# GZCLP Workout Tracker

A Flask-based web application for tracking GZCLP (Generalized Strength and Conditioning Linear Progression) workouts.

## Features

- **User Authentication**: Secure login/registration system with password hashing
- **Program Management**: Configure your GZCLP program with T1, T2, and T3 exercises
- **Workout Tracking**: Log your workouts with automatic weight calculations
- **Multiple Color Themes**: Choose from 5 different color schemes
- **Responsive Design**: Works on desktop and mobile devices

## GZCLP Program Structure

The GZCLP program divides workouts into three tiers:

- **T1 (Main Compound)**: 85-100% TM, 3×5 reps, 3-5 min rest
- **T2 (Secondary)**: 65-85% TM, 3×10 reps, 2-3 min rest  
- **T3 (Assistance)**: <65% TM, 3×15+ reps, 60-90 sec rest

## Color Scheme Options

1. **Dark Orange** (Default): Gym-focused dark theme with orange accents
2. **Blue Gray**: Clean, professional look with blue and gray
3. **Green Black**: Natural, energetic theme with green and black
4. **Purple Dark**: Modern, high-tech purple and dark theme
5. **Red White**: Bold, intense red and white theme

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd GZCLP
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the application**:
   Open your browser and go to `http://localhost:5001`

## Usage

1. **Register**: Create a new account with username and password
2. **Login**: Sign in to access your personal dashboard
3. **Settings**: Configure your GZCLP program by adding exercises to each tier
4. **Track Workouts**: Log your completed exercises with sets, reps, and weights
5. **Monitor Progress**: View your workout history and progression

## Database

The application uses SQLite for data storage with the following models:

- **User**: Stores user credentials and profile information
- **Program**: User's workout programs
- **Exercise**: Individual exercises with tier and training max
- **WorkoutLog**: Historical workout data

## Security Notes

- Passwords are hashed using Werkzeug's security functions
- User sessions are managed securely
- Each user's data is isolated from others

## Future Enhancements

- OAuth integration for social login
- Advanced analytics and progress tracking
- Exercise video demonstrations
- Mobile app development
- Community features and workout sharing

## Technology Stack

- **Backend**: Flask, SQLAlchemy, WTForms
- **Frontend**: Bootstrap 5, Font Awesome icons
- **Database**: SQLite
- **Styling**: Custom CSS with CSS variables for theming

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the MIT License.

