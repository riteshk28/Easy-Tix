# Try Memurai first, fallback to Redis
try:
    broker_url = 'redis://localhost:6379/0'
    result_backend = 'redis://localhost:6379/0'
except:
    # Memurai typically uses the same port
    broker_url = 'redis://localhost:6379/0'
    result_backend = 'redis://localhost:6379/0'

task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
enable_utc = True 