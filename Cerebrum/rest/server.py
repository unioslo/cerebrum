from api import create_app
import restconfig

app = create_app(restconfig)

if __name__ == '__main__':
    app.run(host=app.config['HOST'],
            port=app.config['PORT'])
