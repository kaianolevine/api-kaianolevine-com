## [1.52.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.52.1...v1.52.2) (2026-09-08)


### Bug Fixes

* modifying notification behavior ([d4a5b77](https://github.com/mini-app-polis/api-kaianolevine-com/commit/d4a5b77699e4905370182a1cebfff51dcf115005))

## [1.52.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.52.0...v1.52.1) (2026-09-08)


### Bug Fixes

* **deps:** bump openai from 1.109.1 to 3.8.0 ([af703db](https://github.com/mini-app-polis/api-kaianolevine-com/commit/af703db784b1686aefbbfad25fae7c4da2e5db54))

# [1.52.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.7...v1.52.0) (2026-09-08)


### Features

* adding notification processing from github and custom ([cc02540](https://github.com/mini-app-polis/api-kaianolevine-com/commit/cc0254074eb3136ded9951cd2088a59848a8b1a9))

## [1.51.7](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.6...v1.51.7) (2026-09-07)


### Bug Fixes

* remove uv.lock from release (PY-017) ([0e853b4](https://github.com/mini-app-polis/api-kaianolevine-com/commit/0e853b43abcfd4d6abd4e3a82c8295a4c16240a3))

## [1.51.6](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.5...v1.51.6) (2026-09-07)


### Bug Fixes

* include uv.lock in release artifacts ([bb3eadf](https://github.com/mini-app-polis/api-kaianolevine-com/commit/bb3eadf067700b679977f66b82be59277ab4fdbc))

## [1.51.5](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.4...v1.51.5) (2026-09-06)


### Bug Fixes

* **release:** source the version from a committed file instead of pyproject.toml ([4a6cf3c](https://github.com/mini-app-polis/api-kaianolevine-com/commit/4a6cf3c499aaffe72e5a522c252a1710df70b544))

## [1.51.4](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.3...v1.51.4) (2026-09-05)


### Bug Fixes

* **deps:** consume miniapppolis-common-utils and miniapppolis-identity from PyPI ([f98d769](https://github.com/mini-app-polis/api-kaianolevine-com/commit/f98d769a5a0892afdd118f31108073e6b92fcd89))

## [1.51.3](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.2...v1.51.3) (2026-09-05)


### Bug Fixes

* **wcs:** mint citation links in the shape the site can actually serve ([a78232d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a78232d5f3f03135a6f7d9f0d3ea2107a49c7511))

## [1.51.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.1...v1.51.2) (2026-09-05)


### Bug Fixes

* **wcs:** take profile identity from the verified token, not the request body ([5f4b907](https://github.com/mini-app-polis/api-kaianolevine-com/commit/5f4b9078352e37c8342debf3c2ee73a6f8368890))

## [1.51.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.51.0...v1.51.1) (2026-09-04)


### Bug Fixes

* **deps:** bump anthropic from 0.125.0 to 1.3.0 ([62d0540](https://github.com/mini-app-polis/api-kaianolevine-com/commit/62d0540bd73545252ffdacb5a473a8774d04c730))
* **deps:** bump openai from 1.109.1 to 3.6.0 ([50a58ef](https://github.com/mini-app-polis/api-kaianolevine-com/commit/50a58efc2884fc6c709dfe73dd38e7082bcef519))
* **deps:** bump pre-commit from 3.8.0 to 4.6.2 ([db6abfe](https://github.com/mini-app-polis/api-kaianolevine-com/commit/db6abfe0a2e263c544d41aba11450fc20c240e3c))
* **deps:** repair the lockfile a Dependabot branch merge corrupted ([7695d97](https://github.com/mini-app-polis/api-kaianolevine-com/commit/7695d979881806dd412751e1c18e227646b50f43)), closes [#7](https://github.com/mini-app-polis/api-kaianolevine-com/issues/7)
* **git:** never three-way merge a lockfile ([a8d205a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a8d205abf4aed2427ecdf5c40847ee9bd8b5c3bc))

# [1.51.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.50.0...v1.51.0) (2026-09-04)


### Features

* **deps:** automate dependency updates ([a2e12e9](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a2e12e95ab19b6c50ea4e75abb30928b45bfb9b5))

# [1.50.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.49.1...v1.50.0) (2026-09-04)


### Features

* **ops:** separate the migration role from the request path ([2199104](https://github.com/mini-app-polis/api-kaianolevine-com/commit/219910441a394154509d34d404c0785b65ab6098))

## [1.49.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.49.0...v1.49.1) (2026-09-04)


### Bug Fixes

* **logging,docs:** shared logger in identity_registry, header parity noted ([b623b6a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/b623b6aff92a65ea0e6fd709694b0b3822344aa7))

# [1.49.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.48.0...v1.49.0) (2026-09-04)


### Features

* **deploy:** declare resource ceilings (placeholder values) ([63e4dc5](https://github.com/mini-app-polis/api-kaianolevine-com/commit/63e4dc56518402763021f2e2e791b3d001a16540))

# [1.48.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.47.1...v1.48.0) (2026-09-04)


### Features

* **deploy:** declare the restart policy alongside the start command ([09842fb](https://github.com/mini-app-polis/api-kaianolevine-com/commit/09842fbcc13e48f3ba7adecd89c40973c43640d8))

## [1.47.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.47.0...v1.47.1) (2026-09-04)


### Bug Fixes

* **identity:** declare whoami's response shape and document the handler ([08e115b](https://github.com/mini-app-polis/api-kaianolevine-com/commit/08e115b8fc2b14647222f2e19547667772bebb4b))

# [1.47.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.46.4...v1.47.0) (2026-09-03)


### Bug Fixes

* **deps:** widen two caps and refresh the lock to clear 43 advisories ([924ee54](https://github.com/mini-app-polis/api-kaianolevine-com/commit/924ee54eb7ffd3d991a82aab19d83ee8bbc274b3))


### Features

* **security:** call the shared security workflow ([a8adb23](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a8adb23643e757cebdcdc7b159ab235d0786c6ed))

## [1.46.4](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.46.3...v1.46.4) (2026-09-02)


### Bug Fixes

* **auth:** restore admin-only access to the four gaps endpoints ([703aa8e](https://github.com/mini-app-polis/api-kaianolevine-com/commit/703aa8ed8d478569de4bcf05e4a6d166bd2a9b6c))

## [1.46.3](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.46.2...v1.46.3) (2026-09-02)


### Bug Fixes

* **auth:** stop granting the unfiltered corpus to every signed-in user ([c5600b6](https://github.com/mini-app-polis/api-kaianolevine-com/commit/c5600b669ad7a13c48d686661e402bb87b51fb69))

## [1.46.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.46.1...v1.46.2) (2026-09-02)


### Bug Fixes

* **auth:** enumerate all three authenticated-only routes in the docstring ([3757ccf](https://github.com/mini-app-polis/api-kaianolevine-com/commit/3757ccf47f59bed0a9b727a701d022ac0d4e8675))

## [1.46.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.46.0...v1.46.1) (2026-09-02)


### Bug Fixes

* **auth:** remove the Clerk machine path and its dead guards ([7f9cad0](https://github.com/mini-app-polis/api-kaianolevine-com/commit/7f9cad074b66e60d1124b96f6e1b575acb89fadc))

# [1.46.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.45.2...v1.46.0) (2026-09-02)


### Features

* **identity:** enforce a scope on every authenticated endpoint ([819b3dd](https://github.com/mini-app-polis/api-kaianolevine-com/commit/819b3dd19ea523f9d7494cab20e857c78d63d558))

## [1.45.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.45.1...v1.45.2) (2026-09-02)


### Bug Fixes

* **deps:** pin identity v1.1.1 ([7920cdf](https://github.com/mini-app-polis/api-kaianolevine-com/commit/7920cdf693bacc057adb807d2fdcd84e234d1156))

## [1.45.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.45.0...v1.45.1) (2026-09-02)


### Bug Fixes

* **deps:** relock identity v1.1.0 and common-python-utils v3.2.0 ([d856380](https://github.com/mini-app-polis/api-kaianolevine-com/commit/d856380096a7560b362c7ec47c1f673ee07d975c))

# [1.45.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.44.0...v1.45.0) (2026-09-02)


### Features

* **identity:** declare all five cogs and add the wcs-writer role ([45fa008](https://github.com/mini-app-polis/api-kaianolevine-com/commit/45fa00836d4a286cc847ed13ba7b61c2582d206c))

# [1.44.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.43.1...v1.44.0) (2026-09-02)


### Bug Fixes

* finalizing identity procresses ([ec747d5](https://github.com/mini-app-polis/api-kaianolevine-com/commit/ec747d5660a80155410547a551de79c1947643a2))


### Features

* fix api ([954f016](https://github.com/mini-app-polis/api-kaianolevine-com/commit/954f016fb93da0f40ab8d5be6e2c777c244e5f47))

## [1.43.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.43.0...v1.43.1) (2026-09-01)


### Bug Fixes

* filling out auth ([0d0d3da](https://github.com/mini-app-polis/api-kaianolevine-com/commit/0d0d3da24e1293cd7557362f5f231e26db98e526))

# [1.43.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.42.2...v1.43.0) (2026-09-01)


### Features

* **identity:** pin identity v1.0.1, add principal seed script ([c6f9e76](https://github.com/mini-app-polis/api-kaianolevine-com/commit/c6f9e7646d919b59e53a915cc9e9eaee91dcd53b))
* migrating auth ([5449bee](https://github.com/mini-app-polis/api-kaianolevine-com/commit/5449beeeab903fcdb46e687df10db1280cb089eb))

## [1.42.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.42.1...v1.42.2) (2026-06-07)


### Bug Fixes

* adjusting tests for conformnce checker ([4ec3343](https://github.com/mini-app-polis/api-kaianolevine-com/commit/4ec3343e8bd78dd434781c407109cd3dd795e9d4))

## [1.42.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.42.0...v1.42.1) (2026-05-29)


### Bug Fixes

* **composition:** write one extraction row per item; derive co-taught attribution at read time ([b0aff1d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/b0aff1d6478a8b45b697fd2379d9ad937dea613c))

# [1.42.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.41.0...v1.42.0) (2026-05-29)


### Features

* **wcs:** include resolved entity/instructor names in source view response ([e1e893a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/e1e893a0dc0e95de8f8eda20c54bfcbd9fc2dd6a))

# [1.41.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.40.1...v1.41.0) (2026-05-28)


### Features

* GET /v1/wcs/wiki/export is admin-only, returns full corpus ([58ac1ca](https://github.com/mini-app-polis/api-kaianolevine-com/commit/58ac1ca40cf927507210be45150c1621df299bdd))
* require_wcs_service for machine callers; export accepts admin OR service ([759875b](https://github.com/mini-app-polis/api-kaianolevine-com/commit/759875b9fd557d8ca4f298510eb04cbc823d4110))
* require_wcs_service; export is cog-only, returns full corpus ([91ffa16](https://github.com/mini-app-polis/api-kaianolevine-com/commit/91ffa161281c8c3a01748faf50de94f8877bc97a))

## [1.40.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.40.0...v1.40.1) (2026-05-28)


### Bug Fixes

* expose entity_id on WcsSourceAttributionItem ([297f355](https://github.com/mini-app-polis/api-kaianolevine-com/commit/297f355f2e07e6371a8a5ff5a39d92a3a0ccf47f))

# [1.40.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.39.0...v1.40.0) (2026-05-28)


### Features

* substrate admin read + mutation endpoints; remove admin visibility bypass ([8ea1d05](https://github.com/mini-app-polis/api-kaianolevine-com/commit/8ea1d0521596bc6e71fe23d9fb58f6803484d428))

# [1.39.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.38.1...v1.39.0) (2026-05-27)


### Features

* enforce transcript uniqueness with idempotent re-ingestion ([7badb68](https://github.com/mini-app-polis/api-kaianolevine-com/commit/7badb68ab3d1ad199c84f11a6f73952436a35cae))

## [1.38.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.38.0...v1.38.1) (2026-05-27)


### Bug Fixes

* remove max_length caps from extraction request schemas ([0fbd5f4](https://github.com/mini-app-polis/api-kaianolevine-com/commit/0fbd5f40147ecbad8bcb8223a33451e799778caa))

# [1.38.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.37.1...v1.38.0) (2026-05-27)


### Features

* automated migration application via scripts/apply_migrations.py ([be1c51c](https://github.com/mini-app-polis/api-kaianolevine-com/commit/be1c51c57325172786d5815a7e7c0f722ed35447))

## [1.37.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.37.0...v1.37.1) (2026-05-22)


### Bug Fixes

* testing and doc chnage only to address pipeline findings for DOC-010, DOC-007, DOC-006, and TEST-010 ([a54523d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a54523d6118cb84fd057f0223d7d6e22d3bc8340))

# [1.37.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.36.0...v1.37.0) (2026-05-20)


### Features

* WCS entity substrate endpoints — write, read, corrections, additions ([5b009ad](https://github.com/mini-app-polis/api-kaianolevine-com/commit/5b009ad3b52302f3e3291266ae263e1f72de5434))

# [1.36.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.35.0...v1.36.0) (2026-05-20)


### Features

* WCS entity substrate foundation — models, schemas, composition service ([70bb326](https://github.com/mini-app-polis/api-kaianolevine-com/commit/70bb326fcc226326747193badad64fa085659742))

# [1.35.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.34.4...v1.35.0) (2026-05-20)


### Features

* migration for updated notes processing and design support docs ([2f613cb](https://github.com/mini-app-polis/api-kaianolevine-com/commit/2f613cbe0451d2f51a2e474b7393413b3b476738))

## [1.34.4](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.34.3...v1.34.4) (2026-05-18)


### Bug Fixes

* allowing standards to be none in report ([11a3626](https://github.com/mini-app-polis/api-kaianolevine-com/commit/11a3626adec41f26ffe595407a87a3f43d6fc4aa))

## [1.34.3](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.34.2...v1.34.3) (2026-05-17)


### Bug Fixes

* addressing eval findings ([b8bc09f](https://github.com/mini-app-polis/api-kaianolevine-com/commit/b8bc09f1a66c5f44213282770cd855e0f40e5a0c))
* addressing eval findings ([46d18a5](https://github.com/mini-app-polis/api-kaianolevine-com/commit/46d18a52f90faaeb59f1e1e88184079d0d83de8a))

## [1.34.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.34.1...v1.34.2) (2026-05-17)


### Bug Fixes

* pipeline findings ([336f614](https://github.com/mini-app-polis/api-kaianolevine-com/commit/336f6143981f1c1fa24872a65d868edae61b49b8))

## [1.34.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.34.0...v1.34.1) (2026-05-17)


### Bug Fixes

* removing admin block for notes/all endpoint ([8c87e2f](https://github.com/mini-app-polis/api-kaianolevine-com/commit/8c87e2f6a831530c27610b640ded906ed2f351d3))

# [1.34.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.33.3...v1.34.0) (2026-05-15)


### Features

* adding not data editing ([4b4918e](https://github.com/mini-app-polis/api-kaianolevine-com/commit/4b4918e42bed02ba0b13c2de8eabdd5ba552e66f))

## [1.33.3](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.33.2...v1.33.3) (2026-05-12)


### Bug Fixes

* **evaluations:** coalesce evaluated_at with created_at and order most-recent-first ([237d877](https://github.com/mini-app-polis/api-kaianolevine-com/commit/237d877ca61936b072b5bcaab0ff184e6b9cfa40))

## [1.33.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.33.1...v1.33.2) (2026-05-11)


### Bug Fixes

* remove caching ([fe96a87](https://github.com/mini-app-polis/api-kaianolevine-com/commit/fe96a8706396f83e5a1d36d79fa7e0599db731e8))

## [1.33.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.33.0...v1.33.1) (2026-05-11)


### Bug Fixes

* adding price visibility ([8d46886](https://github.com/mini-app-polis/api-kaianolevine-com/commit/8d46886861d25c0da0d22d4bd37985ff938c2cdb))

# [1.33.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.32.0...v1.33.0) (2026-05-11)


### Features

* adding antropic cahcing ([e96def9](https://github.com/mini-app-polis/api-kaianolevine-com/commit/e96def9b6d9309b0031bf7136862f1c0d11e7318))

# [1.32.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.31.0...v1.32.0) (2026-05-11)


### Features

* providing estimated price information on prompts ([4f0670a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/4f0670a42dc69a8a18b0c79f1e7e90c104adabbb))

# [1.31.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.30.2...v1.31.0) (2026-05-11)


### Features

* adding depth to the searches ([fe8b93f](https://github.com/mini-app-polis/api-kaianolevine-com/commit/fe8b93ffbfe94528d9e2f526f2ec4db2e187cdb8))

## [1.30.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.30.1...v1.30.2) (2026-05-10)


### Bug Fixes

* eval findings warning ([93e2650](https://github.com/mini-app-polis/api-kaianolevine-com/commit/93e265074047b2659fc3e739d62c0e1b192ab05c))

## [1.30.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.30.0...v1.30.1) (2026-05-10)


### Bug Fixes

* models ([48f31b8](https://github.com/mini-app-polis/api-kaianolevine-com/commit/48f31b8da74f2de1e9c04c031dffb85d58cea3b6))
* models ([4471ebc](https://github.com/mini-app-polis/api-kaianolevine-com/commit/4471ebc37f32ab5d8b9ab575e9f691b71bf5831f))
* tests ([f1607f9](https://github.com/mini-app-polis/api-kaianolevine-com/commit/f1607f98308bcc759f7631f0a052b96a08a82c3f))

# [1.30.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.29.0...v1.30.0) (2026-05-10)


### Features

* chunk citations link to underlying note instead of transcript reader ([42e8514](https://github.com/mini-app-polis/api-kaianolevine-com/commit/42e8514c07f88755520e4fcffe5461430f91b1af)), closes [#chunk-N](https://github.com/mini-app-polis/api-kaianolevine-com/issues/chunk-N)

# [1.29.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.28.3...v1.29.0) (2026-05-10)


### Features

* WCS Q&A agent with vector retrieval and eval harness ([451d94b](https://github.com/mini-app-polis/api-kaianolevine-com/commit/451d94b775c640523a504dd7a2108a32301b8c64))

## [1.28.3](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.28.2...v1.28.3) (2026-04-22)


### Bug Fixes

* re-lock uv.lock and close AUTH-002 ([f297126](https://github.com/mini-app-polis/api-kaianolevine-com/commit/f2971267bcdbe0badc2682b6385175fd1274d150))
* re-lock uv.lock in semantic-release prepare step ([6fadb2d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/6fadb2df9d6763a1e9a62b67379e52ed8c5e67fa))

## [1.28.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.28.1...v1.28.2) (2026-04-22)


### Bug Fixes

* migrate Railway builder from Nixpacks to Railpack ([b4f985f](https://github.com/mini-app-polis/api-kaianolevine-com/commit/b4f985fe10b2d94529fafa0623f7f81bc95d97a3))

## [1.28.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.28.0...v1.28.1) (2026-04-22)


### Bug Fixes

* close pipeline findings (DOC-002, PRIN-005, TEST-013, TEST-010) ([1d5d715](https://github.com/mini-app-polis/api-kaianolevine-com/commit/1d5d715e81edc032ef8cb6adbc20633c6e604ce5))

# [1.28.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.27.2...v1.28.0) (2026-04-20)


### Features

* **config:** declare LOGGING_LEVEL, KAIANO_API_OWNER_ID, STANDARDS_VERSION, HTTP_CLIENT_TIMEOUT_SECS on Settings (CFG-001, CFG-002, TEST-013) ([4a4fc1d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/4a4fc1d35177eb319d2a67a19ace255c026cda77))
* **main:** add /health liveness probe (API-010) ([941f26a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/941f26a6f3579589243e0af0e002ca57659465d8))

## [1.27.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.27.1...v1.27.2) (2026-04-20)


### Bug Fixes

* major doc update for evaluation findings ([5150dab](https://github.com/mini-app-polis/api-kaianolevine-com/commit/5150dabf61f00f51e5abae153accc33dba77ba3c))

## [1.27.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.27.0...v1.27.1) (2026-04-20)


### Bug Fixes

* major doc update for evaluation findings ([dbd111e](https://github.com/mini-app-polis/api-kaianolevine-com/commit/dbd111e9041b3be948ead55e0c1cddd69889b5ef))

# [1.27.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.26.0...v1.27.0) (2026-04-18)


### Features

* reopening live music to public get ([ca2a4f0](https://github.com/mini-app-polis/api-kaianolevine-com/commit/ca2a4f09bcbef7b65280c236aa7a5a94ec02c671))

# [1.26.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.25.1...v1.26.0) (2026-04-18)


### Features

* restore opaque token verification ([43cc08a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/43cc08aae035ebe94b84779b9aa669ce4d4751f4))

## [1.25.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.25.0...v1.25.1) (2026-04-17)


### Bug Fixes

* removing auth required for get flags ([61c5fd1](https://github.com/mini-app-polis/api-kaianolevine-com/commit/61c5fd1d92d9986ecb32854eef64c17b7773d43a))

# [1.25.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.24.0...v1.25.0) (2026-04-17)


### Bug Fixes

* tests to support current functionality ([b17cf57](https://github.com/mini-app-polis/api-kaianolevine-com/commit/b17cf57ebdd2e3e793929bf435040d07a8df6b96))


### Features

* adding admin notes endpoint ([0752c1b](https://github.com/mini-app-polis/api-kaianolevine-com/commit/0752c1b31f8817c9801ee484fe659a0974c03ee5))
* finishing the proper implementation of auth through clerk ([5b89006](https://github.com/mini-app-polis/api-kaianolevine-com/commit/5b8900616d13d20f2749ad72a8413c02016de40b))

# [1.24.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.23.0...v1.24.0) (2026-04-17)


### Features

* upgrade common for auth ([80bffcd](https://github.com/mini-app-polis/api-kaianolevine-com/commit/80bffcd285b5a512cf831ad18db8db5b611a2124))

# [1.23.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.22.0...v1.23.0) (2026-04-17)


### Features

* upgrade common for auth ([798f22a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/798f22a6cb13ffe5c1f44a0aff0e73f5f1fce9cf))

# [1.22.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.21.1...v1.22.0) (2026-04-17)


### Features

* supporting full auth m2m pattern ([125e353](https://github.com/mini-app-polis/api-kaianolevine-com/commit/125e353cf36f97734030590acb1e063348fb28cc))

## [1.21.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.21.0...v1.21.1) (2026-04-16)


### Bug Fixes

* notes auth for admin specifically ([6898396](https://github.com/mini-app-polis/api-kaianolevine-com/commit/68983969a5858accd1ba8c03687d761d2ca93763))

# [1.21.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.20.0...v1.21.0) (2026-04-16)


### Features

* support for new auth for notes permissions ([1111254](https://github.com/mini-app-polis/api-kaianolevine-com/commit/11112547c17f7ff6e92c0f8ae07a844484ee5c3a))

# [1.20.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.19.0...v1.20.0) (2026-04-12)


### Features

* **evaluations:** expand severity to 5 values — add CRITICAL and SUCCESS with CHECK constraint ([3dd62e6](https://github.com/mini-app-polis/api-kaianolevine-com/commit/3dd62e6fb08a83626820aec19c7a0fb102d4a7a6))

# [1.19.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.18.2...v1.19.0) (2026-04-10)


### Bug Fixes

* uv lock ([a9d65c3](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a9d65c3000cbe82a957b417d16d26b6245ad3cc7))


### Features

* **evaluations:** add nullable violation_id field to pipeline_evaluations ([a95b02d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a95b02da53a21c1ee54e19e73fc7d65b50451dd9))

## [1.18.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.18.1...v1.18.2) (2026-04-10)


### Bug Fixes

* uv lock ([a1d7543](https://github.com/mini-app-polis/api-kaianolevine-com/commit/a1d75434b8dc28e144f5ef4c97c40cebb67eaceb))

## [1.18.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.18.0...v1.18.1) (2026-04-10)


### Bug Fixes

* migration details ([69707d7](https://github.com/mini-app-polis/api-kaianolevine-com/commit/69707d76f067071a11a90ba73e7baee4f41e488a))

# [1.18.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.17.0...v1.18.0) (2026-04-10)


### Features

* add root URL redirect to /docs ([f2280e3](https://github.com/mini-app-polis/api-kaianolevine-com/commit/f2280e3281d2bfa2ecef2305ba750f8f7ac1595b))
* resolve real package version into FastAPI constructor and /version endpoint ([e46ba36](https://github.com/mini-app-polis/api-kaianolevine-com/commit/e46ba3668e6ef46ee50cdcc785978f930f71b5c7))

# [1.17.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.16.2...v1.17.0) (2026-04-10)


### Bug Fixes

* uv lock ([4a87e1d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/4a87e1ddd78df68f798dbcb4dca637396bcf517c))


### Features

* add Project Keystone feature flags migration (013) ([0d63e91](https://github.com/mini-app-polis/api-kaianolevine-com/commit/0d63e91f1261a2093d1a00b24fb2caa15550d2a0))


### Performance Improvements

* replace Python years_active aggregation with SQL COUNT DISTINCT ([644b830](https://github.com/mini-app-polis/api-kaianolevine-com/commit/644b8306b645ab27859aea38cd327bbe78928a81))

## [1.16.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.16.1...v1.16.2) (2026-04-10)


### Bug Fixes

* add unique constraint and IntegrityError guard on concurrent set ingest ([934fe8a](https://github.com/mini-app-polis/api-kaianolevine-com/commit/934fe8a3d864f4843b487c24083a5b74bdd9d6a8))

## [1.16.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.16.0...v1.16.1) (2026-04-05)


### Bug Fixes

* owner id for api ([e56ae21](https://github.com/mini-app-polis/api-kaianolevine-com/commit/e56ae21e7f8e869c72096924a0eace324e9317c6))
* tests ([ec8f9fb](https://github.com/mini-app-polis/api-kaianolevine-com/commit/ec8f9fbf971e545b95d8e3a24373e306b03e9def))
* tests ([781ff3b](https://github.com/mini-app-polis/api-kaianolevine-com/commit/781ff3b4f7cae47fb8e818fd86669db66a094e57))

# [1.16.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.15.2...v1.16.0) (2026-04-05)


### Features

* migration to more metadata on processed notes ([20f5034](https://github.com/mini-app-polis/api-kaianolevine-com/commit/20f503402a8bd725b7963067d62c91b374e46fe1))

## [1.15.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.15.1...v1.15.2) (2026-04-03)


### Bug Fixes

* revert ([095a901](https://github.com/mini-app-polis/api-kaianolevine-com/commit/095a9010feabdb94beb50d13d7c106f856ec6990))

## [1.15.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.15.0...v1.15.1) (2026-04-03)


### Bug Fixes

* railway deploy ([ab422a7](https://github.com/mini-app-polis/api-kaianolevine-com/commit/ab422a7984110b1994a6dc656c70c1bb1abf1461))

# [1.15.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.14.2...v1.15.0) (2026-04-03)


### Bug Fixes

* tests ([05710a4](https://github.com/mini-app-polis/api-kaianolevine-com/commit/05710a4f2c680d4442f4cf951aabf54048479f78))


### Features

* adding note ingest support ([b33cc26](https://github.com/mini-app-polis/api-kaianolevine-com/commit/b33cc26aa24ffb3cd47848ab4ec335357df4ec70))

## [1.14.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.14.1...v1.14.2) (2026-04-02)


### Bug Fixes

* updating sentry variable name ([3499d99](https://github.com/mini-app-polis/api-kaianolevine-com/commit/3499d99386620ed825009cf565457a6d3da6c7c5))

## [1.14.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.14.0...v1.14.1) (2026-03-31)


### Bug Fixes

* applies filters to findings and summaries ([3aa8479](https://github.com/mini-app-polis/api-kaianolevine-com/commit/3aa84794ca4f55e504c58d3da3e5b1d0cfa364b4))
* updates from comforance test findings ([ffc7bb9](https://github.com/mini-app-polis/api-kaianolevine-com/commit/ffc7bb9b5252d304e725213d93a429f2f03fa167))

# [1.14.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.13.2...v1.14.0) (2026-03-30)


### Features

* get version, error reporting, evaluations list ([693ba7d](https://github.com/mini-app-polis/api-kaianolevine-com/commit/693ba7d3768cc278b802d764e4e4a50221b0718a))

## [1.13.2](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.13.1...v1.13.2) (2026-03-29)


### Bug Fixes

* apply latest-run filter to evaluations summary ([43b3c99](https://github.com/mini-app-polis/api-kaianolevine-com/commit/43b3c99a4e4aa5e9e6676e60ff609648b9a2891b))

## [1.13.1](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.13.0...v1.13.1) (2026-03-29)


### Bug Fixes

* remove line length requirement ([aa203ee](https://github.com/mini-app-polis/api-kaianolevine-com/commit/aa203ee9f66df36d165e4edf72f97fe45cd63e4e))

# [1.13.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.12.0...v1.13.0) (2026-03-28)


### Features

* major support of spotify endpoint ([32431d7](https://github.com/mini-app-polis/api-kaianolevine-com/commit/32431d711123d72be01a95fb6bc6f82450251908))

# [1.12.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.11.0...v1.12.0) (2026-03-27)


### Features

* wire mini_app_polis for logging and music normalization ([3a6f8ee](https://github.com/mini-app-polis/api-kaianolevine-com/commit/3a6f8eef3eb3a1375744b74b7ff9eca0922756d2))

# [1.11.0](https://github.com/mini-app-polis/api-kaianolevine-com/compare/v1.10.0...v1.11.0) (2026-03-27)


### Features

* name and location restructure ([86c4c44](https://github.com/mini-app-polis/api-kaianolevine-com/commit/86c4c44a111471b2ba67728a45687f6839d0033c))

# [1.10.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.9.0...v1.10.0) (2026-03-27)


### Features

* reverting auth ([e464cee](https://github.com/kaianolevine/api-kaianolevine-com/commit/e464cee0a7793b2e6c421a5e8614671eb95457e4))

# [1.9.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.8.0...v1.9.0) (2026-03-27)


### Features

* pre commit cleanup ([1e84439](https://github.com/kaianolevine/api-kaianolevine-com/commit/1e844394f1b70a82823ddeebac086b82187d8dbb))

# [1.8.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.7.0...v1.8.0) (2026-03-27)


### Features

* adding clerk functionality ([3ad8a68](https://github.com/kaianolevine/api-kaianolevine-com/commit/3ad8a68442577ef9f7d44164377b3c25ff191b5c))

# [1.7.0](https://github.com/kaianolevine/api-kaianolevine-com/compare/v1.6.1...v1.7.0) (2026-03-26)


### Features

* adding resume endpoint to api from legacy api ([77f160c](https://github.com/kaianolevine/api-kaianolevine-com/commit/77f160cbff15fc52ec541450c0af6f61f25e5efd))

## [1.6.1](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.6.0...v1.6.1) (2026-03-26)


### Bug Fixes

* contact ([4f87db5](https://github.com/kaianolevine/deejay-marvel-api/commit/4f87db5f83a8f0e3058a2bf86ccf12ada4117e64))

# [1.6.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.5.1...v1.6.0) (2026-03-26)


### Features

* migrating legacy api contact to this api for final migration of legacy functionality ([f9568db](https://github.com/kaianolevine/deejay-marvel-api/commit/f9568db6099f6f481b9886e6bf98f447de2138f8))

## [1.5.1](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.5.0...v1.5.1) (2026-03-24)


### Bug Fixes

* adding duplicate detection at the api layer ([f8a54e6](https://github.com/kaianolevine/deejay-marvel-api/commit/f8a54e682e23531f9b7cc333833a861f7c1ff076))

# [1.5.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.4.0...v1.5.0) (2026-03-23)


### Features

* adding flow name information ([e29fee7](https://github.com/kaianolevine/deejay-marvel-api/commit/e29fee71e5d0cd6607d1c1d69ca175e5a274c5ee))

# [1.4.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.3.0...v1.4.0) (2026-03-23)


### Features

* migration + schema + both routers (evaluations and webhook) ([72f63d9](https://github.com/kaianolevine/deejay-marvel-api/commit/72f63d971633e5e2dd67a09a3d619891e86e4be4))

# [1.3.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.2.1...v1.3.0) (2026-03-23)


### Features

* Adding webhook endpoints for prefect ([41d05bb](https://github.com/kaianolevine/deejay-marvel-api/commit/41d05bbad64c0e1ee68ccfd4bba52179bd0e234b))

## [1.2.1](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.2.0...v1.2.1) (2026-03-23)


### Bug Fixes

* use pg_insert unconditionally in live plays router ([1455f73](https://github.com/kaianolevine/deejay-marvel-api/commit/1455f7324c3f6464b71b92e93f69e0ef9819abad))

# [1.2.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.1.0...v1.2.0) (2026-03-23)


### Features

* fix inner joins to handle nullable set_id for orphaned live tracks ([8e8f093](https://github.com/kaianolevine/deejay-marvel-api/commit/8e8f0935abf8fe64fbc3c76d4f838e774b1f7f8d))

# [1.1.0](https://github.com/kaianolevine/deejay-marvel-api/compare/v1.0.0...v1.1.0) (2026-03-23)


### Features

* add live play history ingest and recent plays endpoint ([3879193](https://github.com/kaianolevine/deejay-marvel-api/commit/3879193b086327b5b657d1601d08efb6f04cd697))

# 1.0.0 (2026-03-22)


### Bug Fixes

* add missing endpoints to CORS documentation ([3175cd6](https://github.com/kaianolevine/deejay-marvel-api/commit/3175cd6c506b61091e613eecdf93b538876c1d96))

# Changelog

## [0.3.1] - 2026-03-19
### Added
- track_count to SetListItem and SetDetail responses

## [0.3.0] - 2026-03-19
### Added
- CI workflow (lint + test on every push and PR)
- feature_flags table with three initial flags seeded
- GET /v1/flags and PATCH /v1/flags/{name} endpoints
- Flag check on ingest endpoint via is_enabled() service

## [0.2.0] - 2026-03-19
### Added
- Expanded pipeline_evaluations table with structured fields
  (run_id, finding, suggestion, standards_version, evaluated_at)
- POST /v1/evaluations accepts structured PipelineEvaluationCreate
- GET /v1/evaluations and GET /v1/evaluations/summary endpoints

## [0.1.6] - 2026-03-19
### Added
- CORSMiddleware configurable via CORS_ORIGINS environment variable

## [0.1.5] - 2026-03-19
### Added
- track_count field on SetListItem and SetDetail responses

## [0.1.3] - 2026-03-18
### Changed
- Redefined data_quality to use 4 enrichment fields only
  (genre, length_secs, bpm, release_year)

## [0.1.2] - 2026-03-18
### Added
- Historical data migration script (now removed — replaced by
  POST /v1/admin/migrate endpoint pattern)

## [0.1.1] - 2026-03-18
### Added
- Missing CSV columns: remix, label, comment
- Fixed play_order nullability

## [0.1.0] - 2026-03-18
### Added
- Initial implementation. FastAPI service with PostgreSQL via
  SQLAlchemy async. Five tables: sets, tracks, track_catalog,
  pipeline_evaluations, feature_flags. All endpoints implemented.
  Reconciliation and normalization services. Contract tests for
  all endpoints.
