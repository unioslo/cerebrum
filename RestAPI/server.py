from api import create_app
import config

app = create_app(config)

if __name__ == '__main__':
    app.run(host=app.config['HOST'],
            port=app.config['PORT'])
