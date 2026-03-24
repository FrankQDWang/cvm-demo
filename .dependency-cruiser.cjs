/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  options: {
    tsConfig: {
      fileName: 'tsconfig.base.json',
    },
    includeOnly: '^apps/|^libs/ts/',
    exclude: '(^|/)(dist|out-tsc|coverage)/',
    doNotFollow: {
      path: 'node_modules',
    },
    combinedDependencies: true,
  },
  forbidden: [
    {
      name: 'no-cycles',
      severity: 'error',
      from: {},
      to: {
        circular: true,
      },
    },
    {
      name: 'no-web-user-to-other-apps',
      severity: 'error',
      from: {
        path: '^apps/web-user/src/',
      },
      to: {
        path: '^apps/(web-ops|web-evals)/src/',
      },
    },
    {
      name: 'no-web-ops-to-other-apps',
      severity: 'error',
      from: {
        path: '^apps/web-ops/src/',
      },
      to: {
        path: '^apps/(web-user|web-evals)/src/',
      },
    },
    {
      name: 'no-web-evals-to-other-apps',
      severity: 'error',
      from: {
        path: '^apps/web-evals/src/',
      },
      to: {
        path: '^apps/(web-user|web-ops)/src/',
      },
    },
    {
      name: 'no-apps-direct-generated-client',
      severity: 'error',
      from: {
        path: '^apps/[^/]+/src/',
      },
      to: {
        path: '^libs/ts/api-client-generated/',
      },
    },
    {
      name: 'only-platform-api-client-may-use-generated-client',
      severity: 'error',
      from: {
        path: '^libs/ts/(?!platform-api-client|api-client-generated)[^/]+/',
      },
      to: {
        path: '^libs/ts/api-client-generated/',
      },
    },
    {
      name: 'no-generated-deep-imports',
      severity: 'error',
      from: {
        path: '^(apps/|libs/ts/platform-api-client/)',
      },
      to: {
        path: '^libs/ts/api-client-generated/src/generated/',
      },
    },
    {
      name: 'no-lib-to-app-dependencies',
      severity: 'error',
      from: {
        path: '^libs/ts/',
      },
      to: {
        path: '^apps/',
      },
    },
  ],
};
