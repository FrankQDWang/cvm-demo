const config = {
  workspaces: {
    'apps/web-user': {
      project: ['src/**/*.ts', 'src/**/*.html'],
    },
    'apps/web-ops': {
      project: ['src/**/*.ts', 'src/**/*.html'],
    },
    'apps/web-evals': {
      project: ['src/**/*.ts', 'src/**/*.html'],
    },
    'libs/ts/platform-api-client': {
      project: ['src/**/*.ts'],
    },
  },
  ignore: ['.repo-harness/**', 'apps/*/public/runtime-config.js'],
  ignoreIssues: {
    'libs/ts/api-client-generated/src/generated/**': ['exports', 'types'],
  },
};

export default config;
