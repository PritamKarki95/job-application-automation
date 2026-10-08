import json
from pathlib import Path
import requests

root = Path(__file__).resolve().parent
path = root / 'companies.json'
data = json.loads(path.read_text(encoding='utf-8'))
templates = {
    'greenhouse': 'https://boards-api.greenhouse.io/v1/boards/{}/jobs',
    'lever': 'https://api.lever.co/v0/postings/{}?mode=json',
    'ashby': 'https://api.ashbyhq.com/posting-api/job-board/{}',
}
results = []
for provider, template in templates.items():
    for name in list(data.get(provider, [])):
        url = template.format(name)
        try:
            response = requests.get(url, timeout=30)
            status = response.status_code
            if status == 404:
                data[provider].remove(name)
            results.append({'provider': provider, 'name': name, 'status': status, 'url': url})
            print(provider, name, status, 'REMOVED' if status == 404 else '', flush=True)
        except requests.RequestException as exc:
            results.append({'provider': provider, 'name': name, 'error': str(exc), 'url': url})
            print(provider, name, type(exc).__name__, flush=True)
path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
(root / 'board-check-results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
