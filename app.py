from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import uuid
import re
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Multi-user testing mode (for simulating multiple learners in different tabs)
MULTI_USER_MODE = os.environ.get('DEBUG', 'False').lower() == 'true' or os.environ.get('MULTI_USER_MODE', 'False').lower() == 'true'

# In-memory storage - matches your Node.js structure exactly
rooms = {}

def validate_room_code(room_code):
    """Validate room code: only letters, numbers, hyphens, 2-10 characters"""
    return bool(re.match(r'^[A-Za-z0-9-]{2,10}$', room_code))

def get_status_symbol(status):
    """Convert status to HTML icon representation"""
    if not status:
        return '&nbsp;'
    
    status_map = {
        'tick': '<i class="fas fa-check-circle tick"></i>',
        'cross': '<i class="fas fa-times-circle cross"></i>',
        'coffee': '<i class="fas fa-mug-hot coffee"></i>',
        'away': '<i class="fas fa-clock away"></i>',
        'smile': '<i class="fas fa-smile smile"></i>',
        'hand-up': '<i class="far fa-hand-paper"></i>',
        'happy': '<i class="fas fa-grin-stars happy"></i><i class="fas fa-grin-stars happy"></i>'
    }
    
    return status_map.get(status, f'<b>{status}</b>')

@app.route('/')
def intro():
    return render_template('intro.html')

@app.route('/join', methods=['POST'])
def join_room():
    room_code = request.form.get('room_code', '').lower().strip()
    role = request.form.get('role')  # 'learner' or 'tutor'
    
    if not room_code or not validate_room_code(room_code):
        return redirect(url_for('intro'))
    
    if role == 'tutor':
        return redirect(url_for('tutor_page', room_code=room_code))
    else:
        return redirect(url_for('learner_page', room_code=room_code))

def get_learner_id():
    # Generate or get learner ID
    if 'learner_id' not in session:
        learner_uuid = str(uuid.uuid4())

        if MULTI_USER_MODE:
            # Each tab gets a unique learner ID for testing
            time_str = datetime.now().strftime('%H:%M:%S')
            learner_uuid += '-'+time_str
        
        # save learner id in Flask session cookie
        session['learner_id'] = learner_uuid

    learner_id = session['learner_id']
    print(learner_id)
    
    return learner_id

@app.route('/<room_code>')
def learner_page(room_code):
    # Block any query parameters for security
    if request.args:
        return "Forbidden", 403
    
    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()
    
    # Initialize room if it doesn't exist
    if room_code not in rooms:
        rooms[room_code] = {
            'code': room_code,
            'description': f'Room {room_code.upper()}',
            'learners': {},  # Dictionary, not array
            'createdDate': datetime.now().isoformat() + 'Z'
        }
    
    learner_id = get_learner_id()
    
    # Find existing learner or create new one
    if learner_id not in rooms[room_code]['learners']:
        rooms[room_code]['learners'][learner_id] = {
            'name': '',
            'isActive': True,
            'lastCommunication': datetime.now().isoformat() + 'Z',
            # These fields get added when learner interacts
            'status': '',
            'answer': '',
            'handUpRank': 0
        }
    
    learner = rooms[room_code]['learners'][learner_id]
    
    return render_template('learner.html', 
                         room=rooms[room_code], 
                         learner=learner,
                         learner_id=learner_id)

@app.route('/<room_code>/tutor')
def tutor_page(room_code):
    # Block any query parameters for security
    if request.args:
        return "Forbidden", 403
    
    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()
    
    # Initialize room if it doesn't exist
    if room_code not in rooms:
        rooms[room_code] = {
            'code': room_code,
            'description': f'Room {room_code}',
            'learners': {},  # Dictionary, not array
            'createdDate': datetime.now().isoformat() + 'Z'
        }
    
    # Convert learners dict to list for template (with status symbols)
    learners_list = []
    for learner_id, learner_data in rooms[room_code]['learners'].items():
        learner = learner_data.copy()
        # Only list active users
        if learner['isActive'] == True:
            learner['id'] = learner_id
            learner['status_symbol'] = get_status_symbol(learner.get('status', ''))
            learners_list.append(learner)
    
    # Create room object for template
    room_for_template = rooms[room_code].copy()
    room_for_template['learners'] = learners_list
    
    return render_template('tutor.html', 
                         room=room_for_template,
                         base_url=request.base_url.replace('/tutor', ''))

# Save the database if in DEBUG mode
def save_db_json():
    if app.debug:
        with open('db.json', 'w') as f:
            json.dump(rooms, f, indent=2, default=str)

@app.route('/<room_code>/update', methods=['POST'])
def update_learner(room_code):
    room_code = room_code.lower()
    learner_id = get_learner_id()
    
    if not validate_room_code(room_code):
        return jsonify({'success': False, 'error': 'Invalid room code'})
    
    if not learner_id or room_code not in rooms:
        return jsonify({'success': False, 'error': 'Invalid session or room'})
    
    if learner_id not in rooms[room_code]['learners']:
        rooms[room_code]['learners'][learner_id] = {
            'name': '',  # starts empty
            'isActive': True,
        }

    data = request.get_json()
    learner = rooms[room_code]['learners'][learner_id]
    
    # Update lastCommunication for any interaction
    learner['isActive'] = True
    learner['lastCommunication'] = datetime.now().isoformat() + 'Z'
    
    # Update learner data
    if 'name' in data:
        learner['name'] = data['name'][:15]  # Max 15 characters
    
    if 'status' in data:
        learner['status'] = data['status']
        
        # Handle hand-up ranking
        if data['status'] == 'hand-up':
            # Count existing hand-ups to determine rank
            hand_up_count = sum(1 for l in rooms[room_code]['learners'].values() 
                              if l.get('status') == 'hand-up' and l != learner)
            learner['handUpRank'] = hand_up_count + 1
        else:
            learner['handUpRank'] = 0
    
    if 'answer' in data:
        learner['answer'] = data['answer'][:20]  # Max 20 characters
    
    save_db_json()
    return jsonify({'success': True, 'timestamp': datetime.now().isoformat()})

@app.route('/<room_code>/clear-status', methods=['POST'])
def clear_all_status(room_code):
    room_code = room_code.lower()
    
    if not validate_room_code(room_code):
        return jsonify({'success': False, 'error': 'Invalid room code'})
    
    if room_code not in rooms:
        return jsonify({'success': False, 'error': 'Room not found'})
    
    # Clear all learner statuses
    for learner in rooms[room_code]['learners'].values():
        learner['status'] = ''
        learner['handUpRank'] = 0
        learner['isActive'] = True
        learner['lastCommunication'] = datetime.now().isoformat() + 'Z'
    
    save_db_json()
    return jsonify({'success': True})

@app.route('/<room_code>/reset-learners', methods=['POST'])
def reset_learners(room_code):
    room_code = room_code.lower()
    
    if not validate_room_code(room_code):
        return jsonify({'success': False, 'error': 'Invalid room code'})
    
    if room_code not in rooms:
        return jsonify({'success': False, 'error': 'Room not found'})

    # Make all learners in the room inactive
    for learner in rooms[room_code]['learners'].values():
        learner['isActive'] = False
        learner['lastCommunication'] = datetime.now().isoformat() + 'Z'
        
    save_db_json()
    return jsonify({'success': True})

@app.route('/<room_code>/poll')
def poll_page(room_code):
    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()
    
    if room_code not in rooms:
        return f"Room {room_code} not found", 404
    
    # Count responses by status - working with dictionary structure
    status_counts = {}
    for learner in rooms[room_code]['learners'].values():
        status = learner.get('status', '')
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
    
    # Find highest count for green highlighting
    highest_count = max(status_counts.values()) if status_counts else 0
    
    # Convert learners dict to list for template
    learners_list = list(rooms[room_code]['learners'].values())
    room_for_template = rooms[room_code].copy()
    room_for_template['learners'] = learners_list
    
    return render_template('poll.html', 
                         room=room_for_template, 
                         status_counts=status_counts,
                         highest_count=highest_count,
                         get_status_symbol=get_status_symbol)

@app.route('/<room_code>/poker')
def poker_page(room_code):
    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()
    
    if room_code not in rooms:
        return f"Room {room_code} not found", 404
    
    # Get poker values (numeric responses) - working with dictionary structure
    poker_values = []
    total_learners = len(rooms[room_code]['learners'])
    
    for learner in rooms[room_code]['learners'].values():
        status = learner.get('status', '')
        if status and (status.replace('.', '').replace('?', '').isdigit() or status == '0.5'):
            try:
                if status == '0.5':
                    poker_values.append(0.5)
                elif status != '?':
                    poker_values.append(float(status))
            except:
                pass
    
    # Calculate statistics
    stats = {}
    consensus = 0
    consensus_votes = 0
    
    if poker_values:
        min_val = min(poker_values)
        max_val = max(poker_values)

        stats['min'] = int(min_val) if min_val % 1 == 0 else min_val
        stats['max'] = int(max_val) if max_val % 1 == 0 else max_val
        stats['count'] = len(poker_values)
        stats['average'] = sum(poker_values) / len(poker_values)
        stats['values'] = sorted(poker_values)
        
        # Calculate consensus (most common value percentage)
        if poker_values:
            most_common_count = max(poker_values.count(x) for x in set(poker_values))
            consensus = round((most_common_count / len(poker_values)) * 100)
            consensus_votes = most_common_count
    
    return render_template('poker.html', 
                         room=rooms[room_code], 
                         stats=stats,
                         total_learners=total_learners,
                         consensus=consensus,
                         consensus_votes=consensus_votes)

@app.route('/about')
def about():
    return render_template('about.html')

@app.context_processor
def utility_processor():
    return dict(get_status_symbol=get_status_symbol)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
