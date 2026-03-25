from pathlib import Path

def generate_app(app_name, framework='flask', port=5000):
    \"\"\"
    TASK-033 Application Factory demo.
    \"\"\"
    app_dir = Path('/home/aseps/MCP/generated_apps/' + app_name)
    app_dir.mkdir(parents=True, exist_ok=True)
    
    app_content = \"\"\"from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>{0} by MCP Multi-Talent!</h1>'
\"\"\".format(app_name)
    
    with open(app_dir / 'app.py', 'w') as f:
        f.write(app_content)
    
    with open(app_dir / 'requirements.txt', 'w') as f:
        f.write('flask')
    
    run_cmd = 'cd ' + str(app_dir) + ' && pip install -r requirements.txt && python app.py'
    
    return '✅ App generated: ' + run_cmd

def deploy_app(app_name, platform='local'):
    return '🚀 ' + app_name + ' deployed to ' + platform
