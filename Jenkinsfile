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
        sh 'docker-compose -f src/cerebrum/docker-compose.test.yml up uio'
      }
    }
  }
  post {
    always {
      junit "src/cerebrum/testresults/*_xunit.xml"
      step([$class: 'CoberturaPublisher',
        autoUpdateHealth: false,
        autoUpdateStability: false,
        coberturaReportFile: 'src/cerebrum/testresults/*_coverage.xml',
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