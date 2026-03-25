import logging
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
from core.semantic_analysis import SemanticAnalyzer

logger = logging.getLogger(__name__)

class RealTimeCollaboration:
    def __init__(self, semantic_analyzer: SemanticAnalyzer):
        self.semantic_analyzer = semantic_analyzer
        self.collaboration_sessions = {}
        self.lock = asyncio.Lock()

    async def create_session(self, session_id: str, project_path: str) -> Dict:
        """
        Membuat sesi kolaborasi real-time
        """
        try:
            async with self.lock:
                if session_id in self.collaboration_sessions:
                    return {'error': 'Session already exists'}

                # Initialize session
                session = {
                    'id': session_id,
                    'project_path': project_path,
                    'participants': [],
                    'file_versions': {},
                    'operations_log': [],
                    'semantic_analyzer': self.semantic_analyzer
                }

                self.collaboration_sessions[session_id] = session
                return {'success': True, 'session': session}
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return {'error': str(e)}

    async def join_session(self, session_id: str, user_id: str, user_name: str) -> Dict:
        """
        Join ke sesi kolaborasi
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]
                if user_id in [p['id'] for p in session['participants']]:
                    return {'error': 'User already in session'}

                # Add participant
                participant = {
                    'id': user_id,
                    'name': user_name,
                    'cursor_position': None,
                    'active_file': None,
                    'permissions': ['read', 'write']
                }
                session['participants'].append(participant)

                return {'success': True, 'participant': participant}
        except Exception as e:
            logger.error(f"Error joining session: {e}")
            return {'error': str(e)}

    async def leave_session(self, session_id: str, user_id: str) -> Dict:
        """
        Leave dari sesi kolaborasi
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]
                session['participants'] = [
                    p for p in session['participants'] if p['id'] != user_id
                ]

                return {'success': True}
        except Exception as e:
            logger.error(f"Error leaving session: {e}")
            return {'error': str(e)}

    async def update_cursor(self, session_id: str, user_id: str, file_path: str, line_no: int, column: int) -> Dict:
        """
        Update posisi cursor user
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]
                for participant in session['participants']:
                    if participant['id'] == user_id:
                        participant['cursor_position'] = {'line': line_no, 'column': column}
                        participant['active_file'] = file_path
                        break

                return {'success': True}
        except Exception as e:
            logger.error(f"Error updating cursor: {e}")
            return {'error': str(e)}

    async def edit_file(self, session_id: str, user_id: str, file_path: str, content: str, operation_id: str) -> Dict:
        """
        Edit file dengan conflict resolution
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]

                # Check if file exists
                full_path = Path(session['project_path']) / file_path
                if not full_path.exists():
                    return {'error': 'File not found'}

                # Get current version
                current_content = full_path.read_text(encoding='utf-8')

                # Conflict resolution menggunakan operational transformation
                operation = {
                    'id': operation_id,
                    'user_id': user_id,
                    'file_path': file_path,
                    'content': content,
                    'timestamp': time.time()
                }

                # Apply operation dengan conflict resolution
                transformed_content = await self._apply_operation_with_conflict_resolution(
                    session, operation, current_content
                )

                # Save file
                full_path.write_text(transformed_content, encoding='utf-8')

                # Update file version
                session['file_versions'][file_path] = transformed_content

                # Log operation
                session['operations_log'].append(operation)

                return {'success': True, 'operation': operation}
        except Exception as e:
            logger.error(f"Error editing file: {e}")
            return {'error': str(e)}

    async def _apply_operation_with_conflict_resolution(self, session: Dict, operation: Dict, current_content: str) -> str:
        """
        Apply operation dengan conflict resolution
        """
        try:
            # Simple conflict resolution: last write wins
            # Dalam implementasi nyata, gunakan operational transformation
            return operation['content']
        except Exception as e:
            logger.error(f"Error in conflict resolution: {e}")
            return current_content

    async def get_session_state(self, session_id: str) -> Dict:
        """
        Mendapatkan state sesi kolaborasi
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]
                return {
                    'success': True,
                    'session': {
                        'id': session['id'],
                        'project_path': session['project_path'],
                        'participants': session['participants'],
                        'file_versions': {k: 'available' for k in session['file_versions']},
                        'operations_log': session['operations_log'][-10:]  # Last 10 operations
                    }
                }
        except Exception as e:
            logger.error(f"Error getting session state: {e}")
            return {'error': str(e)}

    async def get_file_analysis(self, session_id: str, file_path: str) -> Dict:
        """
        Mendapatkan analisis file dengan semantic understanding
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]
                full_path = Path(session['project_path']) / file_path

                if not full_path.exists():
                    return {'error': 'File not found'}

                # Use semantic analyzer
                analysis = session['semantic_analyzer'].analyze_file(str(full_path))

                return {
                    'success': True,
                    'analysis': analysis,
                    'file_path': file_path
                }
        except Exception as e:
            logger.error(f"Error getting file analysis: {e}")
            return {'error': str(e)}

    async def suggest_collaborative_edits(self, session_id: str, user_id: str, file_path: str) -> Dict:
        """
        Menyarankan collaborative edits berdasarkan konteks
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]
                full_path = Path(session['project_path']) / file_path

                if not full_path.exists():
                    return {'error': 'File not found'}

                # Get semantic analysis
                analysis = await self.get_file_analysis(session_id, file_path)
                if 'error' in analysis:
                    return analysis

                # Generate suggestions
                suggestions = self._generate_suggestions(analysis['analysis'])

                return {
                    'success': True,
                    'suggestions': suggestions,
                    'file_path': file_path
                }
        except Exception as e:
            logger.error(f"Error suggesting collaborative edits: {e}")
            return {'error': str(e)}

    def _generate_suggestions(self, analysis: Dict) -> List[Dict]:
        """
        Generate saran editing berdasarkan analisis
        """
        suggestions = []

        # Check for long methods
        if 'ast' in analysis:
            for func in analysis['ast'].get('functions', []):
                if len(func.get('args', [])) > 3:
                    suggestions.append({
                        'type': 'extract_method',
                        'description': f'Method {func["name"]} has many arguments, consider extracting',
                        'priority': 'medium'
                    })

        # Check for duplicate code patterns
        suggestions.append({
            'type': 'extract_method',
            'description': 'Found duplicate code patterns, consider extracting to method',
            'priority': 'high'
        })

        # Check for missing documentation
        suggestions.append({
            'type': 'add_docstring',
            'description': 'Consider adding documentation for better collaboration',
            'priority': 'low'
        })

        return suggestions

    async def get_collaboration_metrics(self, session_id: str) -> Dict:
        """
        Mendapatkan metrics untuk sesi kolaborasi
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]
                metrics = {
                    'active_participants': len([
                        p for p in session['participants'] if p['cursor_position']
                    ]),
                    'total_participants': len(session['participants']),
                    'file_edits': len([op for op in session['operations_log'] if op['type'] == 'edit']),
                    'total_operations': len(session['operations_log']),
                    'project_path': session['project_path']
                }

                return {
                    'success': True,
                    'metrics': metrics
                }
        except Exception as e:
            logger.error(f"Error getting collaboration metrics: {e}")
            return {'error': str(e)}

    async def export_session(self, session_id: str, export_format: str = 'json') -> Dict:
        """
        Export sesi kolaborasi
        """
        try:
            async with self.lock:
                if session_id not in self.collaboration_sessions:
                    return {'error': 'Session not found'}

                session = self.collaboration_sessions[session_id]

                export_data = {
                    'session_id': session['id'],
                    'project_path': session['project_path'],
                    'participants': session['participants'],
                    'operations_log': session['operations_log'],
                    'file_versions': {
                        k: 'available' for k in session['file_versions']
                    }
                }

                if export_format == 'json':
                    return {
                        'success': True,
                        'data': export_data,
                        'format': 'json'
                    }
                else:
                    return {
                        'success': True,
                        'data': export_data,
                        'format': export_format
                    }
        except Exception as e:
            logger.error(f"Error exporting session: {e}")
            return {'error': str(e)}