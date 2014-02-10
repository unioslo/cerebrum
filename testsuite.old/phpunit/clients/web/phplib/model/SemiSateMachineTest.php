<?php
// Copyright 2010 University of Oslo, Norway
// 
// This file is part of Cerebrum.
// 
// Cerebrum is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// 
// Cerebrum is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with Cerebrum. If not, see <http://www.gnu.org/licenses/>.



class SemiStateMachineTest extends PHPUnit_Framework_TestCase
{

    public static function setUpBeforeClass() {
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/SemiStateMachine/State.php';
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/SemiStateMachine.php';
    }

    public function setUp()
    {
        $this->methods_called = array();
        $_SESSION = array();
    }



    public function testConstruct()
    {
        $ssm = new SemiStateMachine('test');
        $this->assertNull($ssm->getState());
        $this->assertFalse((bool) $ssm->getStates());
    }

    public function testStartState() {
        $ssm = new SemiStateMachine('test');
        $ssm->addState('test0');
        $ssm->addState('test1');
        $ssm->addState('test2');
        $ssm->setStartState('test1');
        $this->assertEquals('test1', (String) $ssm->getState());
    }
    public function testFirstStateIsInitial() {
        $ssm = new SemiStateMachine('test');
        $ssm->addState('test0');
        $ssm->addState('test1');
        $ssm->addState('test2');
        $this->assertEquals('test0', (String) $ssm->getState());
    }

    public function testFailingCondition() {
        $mock = $this->getMock('SemiStateMachineDebugClass');
        $mock->expects($this->once())
            ->method('method1')
            ->will($this->returnValue(false));

        $ssm    = new SemiStateMachine('test');
        $start  = $ssm->addState('starter');
        $next   = $ssm->addState('finished');
        $start->addTransition($next, array($mock, 'method1'));
        $this->assertEquals('starter', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('starter', (String) $ssm->getState());
    }

    public function testOKCondition() {
        $mock = $this->getMock('SemiStateMachineDebugClass');
        $mock->expects($this->once())
            ->method('method10')
            ->will($this->returnValue(true));

        $ssm    = new SemiStateMachine('test');
        $start  = $ssm->addState('starter');
        $next   = $ssm->addState('finished');
        $start->addTransition($next, array($mock, 'method10'));

        $this->assertEquals('starter', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('finished', (String) $ssm->getState());
    }

    public function testMoreConditions() {
        $mock = $this->getMock('SemiStateMachineDebugClass');
        $mock->expects($this->once())->method('method1')
            ->will($this->returnValue(true));
        $mock->expects($this->once())->method('method2')
            ->will($this->returnValue(true));

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $next   = $ssm->addState('next_part');

        $state->addTransition($next, array($mock, 'method1'), array($mock, 'method2'));
        $ssm->step();
        $this->assertEquals('next_part', (String) $ssm->getState());
    }

    public function testConditionsInManyStates() {
        $mock = $this->getMock('SemiStateMachineDebugClass');

        # called twice, by $state and $then:
        $mock->expects($this->exactly(2))->method('method1')
            ->will($this->returnValue(true));
        $mock->expects($this->once())->method('method2')
            ->will($this->returnValue(true));
        $mock->expects($this->once())->method('method3')
            ->will($this->returnValue(true));
        $mock->expects($this->once())->method('method4')
            ->will($this->returnValue(true));

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $next   = $ssm->addState('part1');
        $then   = $ssm->addState('part2');
        $finish = $ssm->addState('finished');

        $state->addTransition($next, array($mock, 'method1'), array($mock, 'method2'));
        $next->addTransition($then, array($mock, 'method3'));
        $then->addTransition($finish, array($mock, 'method1'), array($mock, 'method4'));

        $this->assertEquals('init', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('part1', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('part2', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('finished', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('finished', (String) $ssm->getState());
    }

    public function testStateAdd()
    {
        $ssm = new SemiStateMachine('stest');
        $ssm->addState('test0', array($this, 'callMethod0'));
        $this->markTestIncomplete('Need to test if methods are called');
    }

    public function testStateAddObject()
    {
        $ssm = new SemiStateMachine('subtest');
        $ssm->addState(new SemiStateMachine_State('ownstate'));
        $this->assertEquals('ownstate', (String) $ssm->getState());
    }
    public function testStateAddSubclass()
    {
        $mock = $this->getMock('SemiStateMachine_State', null, array('mockup'));
        $ssm = new SemiStateMachine('subtest');
        $ssm->addState($mock);
        $this->assertEquals('mockup', (String) $ssm->getState());
    }

    public function testStateStored()
    {
        $mock = $this->getMock('SemiStateMachineDebugClass');
        for ($i = 0; $i < 10; $i++) {
            $mock->expects($this->any())->method('method' . $i)
                ->will($this->returnValue(true));
        }

        $ssm    = new SemiStateMachine('sessiontest');
        $state  = $ssm->addState('init');
        $next   = $ssm->addState('part1');
        $finish = $ssm->addState('finished');
        $state->addTransition($next, array($mock, 'method1'), array($mock, 'method2'));
        $next->addTransition($finish, array($mock, 'method3'), array($mock, 'method4'));

        $ssm->step();
        $this->assertEquals('part1', (String) $ssm->getState());
        unset($ssm);

        $ssm    = new SemiStateMachine('sessiontest');
        $state  = $ssm->addState('init');
        $next   = $ssm->addState('part1');
        $finish = $ssm->addState('finished');
        $state->addTransition($next, array($mock, 'method1'), array($mock, 'method2'));
        $next->addTransition($finish, array($mock, 'method3'), array($mock, 'method4'));

        // previous steps should be stored in session
        $this->assertEquals('part1', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('finished', (String) $ssm->getState());
        
    }

    public function testTwoStateMachinesNotConflicting()
    {
        $this->markTestIncomplete('Need to test that two machine doesnt get in their way, e.g. in the session');
    }

    public function testReset()
    {
        $mock = $this->getMock('SemiStateMachineDebugClass');
        for ($i = 0; $i < 10; $i++) {
            $mock->expects($this->any())->method('method' . $i)
                ->will($this->returnValue(true));
        }

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $next   = $ssm->addState('part1');
        $finish = $ssm->addState('finished');
        $state->addTransition($next, array($mock, 'method1'), array($mock, 'method2'));
        $next->addTransition($finish, array($mock, 'method3'), array($mock, 'method4'));

        $ssm->step();
        $this->assertEquals('part1', (String) $ssm->getState());
        $ssm->reset();
        $this->assertEquals('init', (String) $ssm->getState());
        $ssm->step();
        $this->assertEquals('part1', (String) $ssm->getState());

    }

    public function testStateInitialEntryAction()
    {
        $mock = $this->getMock('SemiStateMachineDebugClass');
        $mock->expects($this->once())
            ->method('method1')
            ->will($this->returnValue(true));
        $mock->expects($this->never())
            ->method('method2')
            ->will($this->returnValue(true));

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $state->addEntryAction(array($mock, 'method1'));
        $state->addExitAction( array($mock, 'method2'));
        $ssm->step();
    }

    public function testStateActions()
    {
        $mock = $this->getMock('SemiStateMachineDebugClass');
        # conditions are from method0
        for ($i = 0; $i < 10; $i++) {
            $mock->expects($this->any())->method('method' . $i)
                ->will($this->returnValue(true));
        }
        # actions are from method10 to 17
        for ($i = 10; $i < 18; $i++) {
            $mock->expects($this->once())->method('method' . $i);
        }
        $mock->expects($this->never())->method('method20');

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $next   = $ssm->addState('part1');
        $finish = $ssm->addState('finished');

        $state->addTransition($next,  array($mock, 'method0'));
        $next->addTransition($finish, array($mock, 'method1'));

        $state->addEntryAction(array($mock, 'method10'));
        $state->addEntryAction(array($mock, 'method11'));
        $state->addExitAction( array($mock, 'method12'));

        $next->addEntryAction(array($mock, 'method13'));
        $next->addExitAction( array($mock, 'method14'));
        $next->addExitAction( array($mock, 'method15'));

        $finish->addEntryAction(array($mock, 'method16'));
        $finish->addEntryAction(array($mock, 'method17'));
        $finish->addExitAction( array($mock, 'method20'));

        $ssm->step();
        $ssm->step();
        $ssm->step();
        $ssm->step();
    }

    public function testStateSession()
    {
        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $this->assertEquals(false, $state->isActive());
        $state->enterState();
        $this->assertEquals(true, $state->isActive());

        unset($ssm);
        unset($state);

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $this->assertEquals(true, $state->isActive());
    }

    public function testStateTimeNotChanging()
    {
        if (!is_callable('override_function')) {
            $this->markTestSkipped('Could not override time(), time check ' .
                'skipped');
        }

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $state->enterState();
        $this->assertEquals(time(), $state->state_data['time_enter']);

        unset($ssm);
        unset($state);

        # Change time
        printf("\nDebug time: %s\n", time());
        override_function('time', null, 'list($mu, $sec) = explode(" ", microtime()); return $sec + 100;');
        printf("\nDebug new time: %s\n", time());

        $ssm    = new SemiStateMachine('test');
        $state  = $ssm->addState('init');
        $this->assertEquals(time(), $state->state_data['time_enter']);
        $this->markTestIncomplete('Need to test the test');
    }

}

/**
 * Dummy so the mockup works properly.
 */
class SemiStateMachineDebugClass {
    public function method0() {}
    public function method1() {}
    public function method2() {}
    public function method3() {}
    public function method4() {}
    public function method5() {}
    public function method6() {}
    public function method7() {}
    public function method8() {}
    public function method9() {}
    public function method10() {}
    public function method11() {}
    public function method12() {}
    public function method13() {}
    public function method14() {}
    public function method15() {}
    public function method16() {}
    public function method17() {}
    public function method18() {}
    public function method19() {}
    public function method20() {}
}

?>
