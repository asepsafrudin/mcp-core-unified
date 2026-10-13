"""Development Integration Tools (TASK-033; honesty-hardened in TASK-166).

⚠️ EXPERIMENTAL: the scaffold produced by ``generate_app`` is a minimal teaching
sample, not a production application template. ``deploy_app`` is intentionally
NOT implemented and raises instead of pretending to deploy.
"""
from pathlib import Path

REPO_ROOT = Path('/home/aseps/MCP')
DEFAULT_OUTPUT_DIR = REPO_ROOT / 'storage' / 'generated_apps'


def generate_app(app_name, framework='flask', port=5000, output_dir=None):
    """Generate a minimal, runnable Flask scaffold (EXPERIMENTAL).

    This is a teaching/demo scaffold only — it is NOT a production template.
    Output is written under ``storage/generated_apps/<app_name>`` to respect
    storage isolation, overridable via ``output_dir``.

    Returns a dict describing the result. It never claims a deployment.
    """
    base = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    app_dir = base / app_name
    app_dir.mkdir(parents=True, exist_ok=True)

    app_content = """from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>{0} by MCP Multi-Talent!</h1>'

if __name__ == '__main__':
    app.run(port={1})
""".format(app_name, port)

    (app_dir / 'app.py').write_text(app_content, encoding='utf-8')
    (app_dir / 'requirements.txt').write_text('flask\n', encoding='utf-8')

    return {
        'status': 'scaffolded',
        'experimental': True,
        'app_dir': str(app_dir),
        'files': [str(app_dir / 'app.py'), str(app_dir / 'requirements.txt')],
        'run_command': f'cd {app_dir} && pip install -r requirements.txt && python app.py',
    }


def deploy_app(app_name, platform='local'):
    """Deployment is NOT implemented (TASK-166).

    This previously returned a fake ``'🚀 ... deployed ...'`` string. It now fails
    loudly so callers can never mistake an unexecuted deploy for success.
    """
    raise NotImplementedError(
        "deploy_app belum diimplementasi: tidak ada backend deployment nyata "
        f"(diminta untuk app='{app_name}', platform='{platform}')."
    )
