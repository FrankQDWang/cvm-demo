import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import js from '@eslint/js';
import angular from 'angular-eslint';
import globals from 'globals';
import tseslint from 'typescript-eslint';


const rootDir = dirname(fileURLToPath(import.meta.url));

export default tseslint.config(
  {
    ignores: [
      '**/dist/**',
      '**/coverage/**',
      'libs/ts/api-client-generated/**',
    ],
  },
  {
    files: ['apps/*/src/**/*.ts', 'libs/ts/platform-api-client/src/**/*.ts'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.strictTypeChecked,
      ...angular.configs.tsRecommended,
    ],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
      parserOptions: {
        projectService: true,
        tsconfigRootDir: rootDir,
      },
    },
    processor: angular.processInlineTemplates,
    rules: {
      '@angular-eslint/prefer-inject': 'off',
      '@typescript-eslint/ban-ts-comment': [
        'error',
        {
          'ts-check': false,
          'ts-expect-error': true,
          'ts-ignore': true,
          'ts-nocheck': true,
        },
      ],
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-unsafe-assignment': 'error',
      '@typescript-eslint/no-unsafe-member-access': 'error',
      '@typescript-eslint/no-unsafe-return': 'error',
      '@typescript-eslint/only-throw-error': 'error',
    },
  },
  {
    files: ['apps/*/src/**/*.html'],
    extends: [
      ...angular.configs.templateRecommended,
      ...angular.configs.templateAccessibility,
    ],
    rules: {
      '@angular-eslint/template/prefer-control-flow': 'off',
    },
  },
);
