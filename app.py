from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import uuid
import re
import os
import json
from datetime import datetime

# Get the version number
from version import __version__


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-for-development')

# Limit the number of rooms and number of active learners per room
MAX_ROOMS = 10
MAX_LEARNERS_PER_ROOM = 40


# In-memory storage
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
    if 'learner_id' not in session:
        # Generate a unique code for each user
        learner_uuid = str(uuid.uuid4())
        session['learner_id'] = learner_uuid

    return session['learner_id']

@app.route('/<room_code>')
def learner_page(room_code):
    # Block any query parameters for security
    if request.args:
        return "Forbidden", 403
    
    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()
    
    # Show an 404 error if tutor hasn't created the room
    if room_code not in rooms:
        return "Room not found", 404

    # Limit how many active learners can be in a room
    room = rooms[room_code]      
    active_learners = [l for l in room['learners'].values() if l.get('isActive')]
    if len(active_learners) >= MAX_LEARNERS_PER_ROOM:
        return "Room is full", 403  # or 429 Too Many Requests

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
            'handUpRank': 0,
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
        # Limit number of rooms
        if len(rooms) >= MAX_ROOMS:
            return "Maximum number of rooms reached", 403

        rooms[room_code] = {
            'code': room_code,
            'description': f'Room {room_code.upper()}',
            'learners': {},  # Dictionary, not array
            'createdDate': datetime.now().isoformat() + 'Z'
        }
    
    # Convert learners dict to list for template (with status symbols)
    learners_list = []
    for learner_id, learner_data in rooms[room_code]['learners'].items():
        learner = learner_data.copy()
        # Only list active users
        if learner['isActive']:
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
            'handUpRank': 0,
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
            # Get max hand-up value to determine next rank
            existing_ranks = [
                l.get('handUpRank', 0) 
                for l in rooms[room_code]['learners'].values()
                if l.get('status') == 'hand-up' and l != learner
            ]
            next_rank = max(existing_ranks, default=0) + 1
            learner['handUpRank'] = next_rank
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

# Poll sort by the status 
def sort_key(x):
    try:
        return (0, float(x[0]))  # Numeric statuses first, sorted by float value
    except ValueError:
        return (1, x[0])  # case-sensitive sort for non-numeric keys

@app.route('/<room_code>/poll')
def poll_page(room_code):
    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()
    
    if room_code not in rooms:
        return f"Room {room_code} not found", 404
    
    # Count responses by status
    status_counts = {}
    for learner in rooms[room_code]['learners'].values():
        # Skip inactive learners
        if not learner.get('isActive'):
            continue
        status = learner.get('status', '')
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
    
    # Find highest count for green highlighting
    highest_count = max(status_counts.values()) if status_counts else 0
    
    # Get a list of active learners
    learners_list = list(rooms[room_code]['learners'].values())
    learners_list = [
        learner for learner in rooms[room_code]['learners'].values()
        if learner.get('isActive')
    ]
    
    # Convert learners dict to list for template
    room_for_template = rooms[room_code].copy()
    room_for_template['learners'] = learners_list

    # sort status numerically then alphabetically
    sorted_status_counts = sorted(status_counts.items(), key=sort_key)
    
    return render_template('poll.html', 
                         room=room_for_template, 
                         status_counts=status_counts,
                         sorted_status_counts=sorted_status_counts,
                         highest_count=highest_count,
                         get_status_symbol=get_status_symbol)

@app.route("/api")
def block_api_root():
    return "Access to /api is not allowed", 403

@app.route("/api/rooms")
def api_rooms():
    return jsonify(rooms)

@app.route("/api/summary")
def api_room_summary():
    room_summaries = []

    for room_code, room in rooms.items():
        learners = room.get('learners', {}).values()
        active_count = sum(1 for learner in learners if learner.get('isActive'))
        room_summaries.append({
            'code': room_code,
            'description': room.get('description', ''),
            'active_learners': active_count,
            'created_date': room.get('createdDate'),
        })

    return jsonify(room_summaries)

@app.route('/about')
def about():
    return render_template('about.html')

@app.context_processor
def utility_processor():
    return dict(get_status_symbol=get_status_symbol)

@app.route('/version')
def version():
    return __version__, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
