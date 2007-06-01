These tests are not maintained and while some of them might be of some value, someone should
sit down and design a better way to test spine.  I believe that tests should be easier to map
against the code they are testing.

The tests in this directory are more of the integration test types and not unit tests since
they depend on a lot of code and so there can be _many_ reasons why the tests would break.
