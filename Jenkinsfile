#!/usr/bin/env groovy

pipeline {
  agent { label 'evalg' }
  stages {
    stage ('Checkout source code') {
      steps {
        checkout scm
      }
    }
    stage ('Run tests') {
      steps {
        sh '/opt/rh/rh-python36/root/usr/bin/python3.6 testsuite/docker/scripts/ci-test-runner uio uia'
      }
    }
  }
  post {
    always {
      junit "testresults/*_junit.xml"
      step([$class: 'CoberturaPublisher',
        autoUpdateHealth: false,
        autoUpdateStability: false,
        coberturaReportFile: 'testresults/*_coverage.xml',
        failNoReports: false,
        failUnhealthy: false,
        failUnstable: false,
        maxNumberOfBuilds: 0,
        onlyStable: false,
        sourceEncoding: 'ASCII',
        zoomCoverageChart: false])
    }
  }
}