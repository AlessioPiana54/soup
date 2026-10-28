// The end-to-end tests (npm run e2e): the backend of soup-server/tests/e2e_server.py
// on its own port, so the tests never touch a development backend on 8080.
export const environment = {
  production: false,
  v3BaseUrl: 'http://127.0.0.1:8081/api/v3',
  backendOrigin: 'http://127.0.0.1:8081',
  prosLabUrl: 'https://pros.unicam.it/soup/'
};
