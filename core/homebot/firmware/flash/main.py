"""
============================================================
SATURDAY MAIN
System Bootstrap & Service Integration
============================================================

SATURDAY HomeBot Boot Architecture


                ┌─────────────────────┐
                │       CONFIG        │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │      DRIVERS        │
                │ Motors / IMU / etc  │
                └──────────┬──────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        LOCALIZATION   EXPRESSION  COMMUNICATION
              │
              ▼
          AUTONOMY
              │
              ▼
           RUNTIME
              │
              ▼
        MOTOR ARBITRATION


IMPORTANT:

main.py owns dependency injection.

Localization owns spatial awareness.

Autonomy owns navigation decisions.

Runtime owns scheduling and motor arbitration.

Drivers own hardware execution.

============================================================
"""

import gc
import time


# ============================================================
# SYSTEM REGISTRY
# ============================================================

system = {

    "config": None,

    "drivers": None,

    "expression": None,

    "communication": None,

    "localization": None,

    "autonomy": None,

    "runtime": None

}


# ============================================================
# DEFAULT CONFIGURATION
# ============================================================

DEFAULT_CONFIG = {

    "system_name": "SATURDAY",

    "version": "1.0.0",

    # --------------------------------------------------------
    # LOCALIZATION
    # --------------------------------------------------------

    "meters_per_tick": 0.00005,

    "home_file": "saturday_home.json",

    "home_zone_radius": 2.0,

    # --------------------------------------------------------
    # AUTONOMY
    # --------------------------------------------------------

    "default_speed": 40,

    "navigation_timeout": 120000,

    # --------------------------------------------------------
    # RUNTIME
    # --------------------------------------------------------

    "runtime_loop_delay": 20,

    "localization_interval": 50,

    "autonomy_interval": 50,

    "communication_interval": 50,

    "expression_interval": 100,

    "motor_timeout": 500,

    "max_speed": 100,

    # --------------------------------------------------------
    # COMMUNICATION
    # --------------------------------------------------------

    "mqtt_enabled": True,

    # --------------------------------------------------------
    # MEMORY
    # --------------------------------------------------------

    "gc_interval": 30000

}


# ============================================================
# SAFE MODULE IMPORT
# ============================================================

def import_module(
    module_name
):

    try:

        module = __import__(
            module_name
        )

        return module

    except Exception as e:

        print(

            "[BOOT] Module unavailable:",

            module_name,

            e

        )

        return None


# ============================================================
# FIND CLASS
# ============================================================

def find_class(
    module,
    names
):

    if module is None:

        return None

    for name in names:

        try:

            value = getattr(
                module,
                name,
                None
            )

            if value:

                return value

        except Exception:

            pass

    return None


# ============================================================
# MODULE LOADING
# ============================================================

print("")
print("================================================")
print("           SATURDAY SYSTEM BOOT")
print("================================================")
print("")


config_module = import_module(
    "config"
)

drivers_module = import_module(
    "drivers"
)

expression_module = import_module(
    "expression"
)

communication_module = import_module(
    "communication"
)

localization_module = import_module(
    "localization"
)

autonomy_module = import_module(
    "autonomy"
)

runtime_module = import_module(
    "runtime"
)


# ============================================================
# RESOLVE CLASSES
# ============================================================

Config = find_class(

    config_module,

    [

        "Config",

        "SaturdayConfig",

        "SATURDAYConfig"

    ]

)


# ============================================================
# DRIVERS CLASS RESOLUTION
#
# SATURDAY drivers.py owns HardwareManager.
#
# Compatibility aliases may also exist:
#
# Drivers = HardwareManager
#
# Explicit HardwareManager lookup is included FIRST so
# main.py always resolves the physical hardware owner.
# ============================================================

Drivers = find_class(

    drivers_module,

    [

        "HardwareManager",

        "Drivers",

        "Driver",

        "HardwareDrivers",

        "SaturdayDrivers",

        "SATURDAYDrivers"

    ]

)


Expression = find_class(

    expression_module,

    [

        "Expression",

        "ExpressionEngine",

        "SaturdayExpression",

        "SATURDAYExpression"

    ]

)


Communication = find_class(

    communication_module,

    [

        "Communication",

        "CommunicationLayer",

        "SaturdayCommunication",

        "SATURDAYCommunication"

    ]

)


Localization = find_class(

    localization_module,

    [

        "Localization",

        "LocalizationEngine",

        "SaturdayLocalization",

        "SATURDAYLocalization"

    ]

)


Autonomy = find_class(

    autonomy_module,

    [

        "Autonomy",

        "AutonomyEngine",

        "SaturdayAutonomy",

        "SATURDAYAutonomy"

    ]

)


Runtime = find_class(

    runtime_module,

    [

        "Runtime",

        "SaturdayRuntime",

        "SATURDAYRuntime"

    ]

)


# ============================================================
# INITIALIZE CONFIGURATION
# ============================================================

def initialize_config():

    print(
        "[BOOT] Loading configuration..."
    )

    config = None

    # --------------------------------------------------------
    # PRIMARY CONFIGURATION
    #
    # SATURDAY uses a module-based config.py.
    # The module itself is the configuration object.
    # --------------------------------------------------------

    global config_module

    if config_module is not None:

        config = config_module

        print(
            "[BOOT] Central configuration module online"
        )

    # --------------------------------------------------------
    # CLASS-BASED CONFIG COMPATIBILITY
    #
    # Retained for future architecture compatibility.
    # --------------------------------------------------------

    elif Config:

        constructors = [

            lambda: Config(),

            lambda: Config(
                DEFAULT_CONFIG
            )

        ]

        for constructor in constructors:

            try:

                config = constructor()

                break

            except Exception:

                pass

        if config is not None:

            print(
                "[BOOT] Configuration class online"
            )

    # --------------------------------------------------------
    # EMERGENCY FALLBACK
    # --------------------------------------------------------

    if config is None:

        config = dict(
            DEFAULT_CONFIG
        )

        print(
            "[BOOT] WARNING: Using emergency fallback configuration"
        )

    # --------------------------------------------------------
    # REGISTER CONFIGURATION
    # --------------------------------------------------------

    system[
        "config"
    ] = config

    return config
# ============================================================
# INITIALIZE DRIVERS
#
# Hardware lifecycle:
#
# 1. Construct HardwareManager
# 2. Register it in SATURDAY system registry
# 3. Call HardwareManager.begin()
# 4. HardwareManager initializes:
#
#    MotorController
#    UltrasonicSensor
#    IRSensor
#    Bottom2RGB
#    MicrophoneSensor
#    IMUSensor
#    PowerManager
#
# main.py DOES NOT directly initialize individual hardware.
# Hardware ownership remains entirely inside drivers.py.
# ============================================================

def initialize_drivers(
    config
):

    print(
        "[BOOT] Initializing hardware drivers..."
    )

    if Drivers is None:

        print(
            "[BOOT] WARNING: Drivers class unavailable"
        )

        return None

    constructors = [

        lambda: Drivers(
            config=config
        ),

        lambda: Drivers(
            config
        ),

        lambda: Drivers()

    ]

    for constructor in constructors:

        try:

            # ------------------------------------------------
            # CONSTRUCT HARDWARE MANAGER
            # ------------------------------------------------

            drivers = constructor()

            # ------------------------------------------------
            # REGISTER IMMEDIATELY
            # ------------------------------------------------

            system[
                "drivers"
            ] = drivers

            # ------------------------------------------------
            # INITIALIZE PHYSICAL HARDWARE
            #
            # This calls HardwareManager.begin()
            #
            # HardwareManager owns initialization of:
            #
            # motor
            # ultrasonic
            # ir
            # rgb
            # microphone
            # imu
            # power
            # ------------------------------------------------

            initializer = getattr(
                drivers,
                "begin",
                None
            )

            if not callable(
                initializer
            ):

                initializer = getattr(
                    drivers,
                    "initialize",
                    None
                )

            if callable(
                initializer
            ):

                try:

                    results = initializer()

                    print(
                        "[BOOT] Hardware initialization complete"
                    )

                    # ----------------------------------------
                    # MOTOR STATUS
                    # ----------------------------------------

                    try:

                        if isinstance(
                            results,
                            dict
                        ):

                            motor_ready = results.get(
                                "motor",
                                False
                            )

                            print(

                                "[BOOT] Motor subsystem:",

                                "ONLINE"

                                if motor_ready

                                else

                                "OFFLINE"

                            )

                    except Exception:

                        pass

                except Exception as e:

                    print(

                        "[BOOT] Hardware begin warning:",

                        e

                    )

            else:

                print(

                    "[BOOT] WARNING: Drivers has no begin() "

                    "or initialize() method"

                )

            print(
                "[BOOT] Hardware drivers online"
            )

            return drivers

        except Exception as e:

            print(
                "[BOOT] Driver constructor warning:",
                e
            )

            pass

    print(
        "[BOOT] WARNING: Driver initialization failed"
    )

    return None


# ============================================================
# INITIALIZE EXPRESSION
# ============================================================

def initialize_expression(
    config,
    drivers
):

    print(
        "[BOOT] Initializing expression engine..."
    )

    if Expression is None:

        print(
            "[BOOT] Expression unavailable"
        )

        return None

    constructors = [

        lambda: Expression(
            drivers=drivers,
            config=config
        ),

        lambda: Expression(
            config=config
        ),

        lambda: Expression(
            drivers=drivers
        ),

        lambda: Expression()

    ]

    for constructor in constructors:

        try:

            expression = constructor()

            system[
                "expression"
            ] = expression

            print(
                "[BOOT] Expression engine online"
            )

            return expression

        except Exception:

            pass

    print(
        "[BOOT] Expression initialization failed"
    )

    return None


# ============================================================
# INITIALIZE COMMUNICATION
# ============================================================

def initialize_communication(
    config,
    drivers
):

    print(
        "[BOOT] Initializing communication..."
    )

    if Communication is None:

        print(
            "[BOOT] Communication unavailable"
        )

        return None

    constructors = [

        lambda: Communication(
            config=config,
            drivers=drivers
        ),

        lambda: Communication(
            config=config
        ),

        lambda: Communication()

    ]

    for constructor in constructors:

        try:

            communication = constructor()

            system[
                "communication"
            ] = communication

            print(
                "[BOOT] Communication online"
            )

            return communication

        except Exception:

            pass

    print(
        "[BOOT] Communication initialization failed"
    )

    return None


# ============================================================
# INITIALIZE LOCALIZATION
# ============================================================

def initialize_localization(
    config,
    drivers
):

    print(
        "[BOOT] Initializing localization..."
    )

    if Localization is None:

        print(
            "[BOOT] Localization unavailable"
        )

        return None

    constructors = [

        lambda: Localization(

            drivers=drivers,

            config=config

        ),

        lambda: Localization(
            drivers
        ),

        lambda: Localization()

    ]

    for constructor in constructors:

        try:

            localization = constructor()

            system[
                "localization"
            ] = localization

            print(
                "[BOOT] Localization online"
            )

            return localization

        except Exception as e:

            print(
                "[BOOT] Localization constructor warning:",
                e
            )

    print(
        "[BOOT] Localization initialization failed"
    )

    return None


# ============================================================
# INITIALIZE AUTONOMY
# ============================================================

def initialize_autonomy(
    config,
    localization
):

    print(
        "[BOOT] Initializing autonomy..."
    )

    if Autonomy is None:

        print(
            "[BOOT] Autonomy unavailable"
        )

        return None

    constructors = [

        lambda: Autonomy(

            localization=localization,

            config=config

        ),

        lambda: Autonomy(
            localization
        ),

        lambda: Autonomy()

    ]

    for constructor in constructors:

        try:

            autonomy = constructor()

            # Ensure localization injection.

            try:

                autonomy.localization = (
                    localization
                )

            except Exception:

                pass

            system[
                "autonomy"
            ] = autonomy

            print(
                "[BOOT] Autonomous navigation online"
            )

            return autonomy

        except Exception as e:

            print(
                "[BOOT] Autonomy constructor warning:",
                e
            )

    print(
        "[BOOT] Autonomy initialization failed"
    )

    return None


# ============================================================
# INITIALIZE RUNTIME
# ============================================================

def initialize_runtime(

    config,

    drivers,

    autonomy,

    communication,

    expression,

    localization

):

    print(
        "[BOOT] Initializing runtime..."
    )

    if Runtime is None:

        print(
            "[BOOT] CRITICAL: Runtime unavailable"
        )

        return None

    constructors = [

        lambda: Runtime(

            config=config,

            drivers=drivers,

            autonomy=autonomy,

            communication=communication,

            expression=expression,

            localization=localization

        ),

        lambda: Runtime(

            config,

            drivers,

            autonomy,

            communication,

            expression,

            localization

        ),

        lambda: Runtime()

    ]

    for constructor in constructors:

        try:

            runtime = constructor()

            # ------------------------------------------------
            # FORCE DEPENDENCY INJECTION
            # ------------------------------------------------

            runtime.config = config

            runtime.drivers = drivers

            runtime.autonomy = autonomy

            runtime.communication = communication

            runtime.expression = expression

            runtime.localization = localization

            system[
                "runtime"
            ] = runtime

            print(
                "[BOOT] Runtime nervous system online"
            )

            return runtime

        except Exception as e:

            print(
                "[BOOT] Runtime constructor warning:",
                e
            )

    print(
        "[BOOT] CRITICAL: Runtime initialization failed"
    )

    return None


# ============================================================
# CONNECT SUBSYSTEMS
# ============================================================

def connect_subsystems():

    runtime = system.get(
        "runtime"
    )

    communication = system.get(
        "communication"
    )

    autonomy = system.get(
        "autonomy"
    )

    localization = system.get(
        "localization"
    )

    drivers = system.get(
        "drivers"
    )

    if runtime is None:

        return False

    # --------------------------------------------------------
    # COMMUNICATION -> RUNTIME
    # --------------------------------------------------------

    if communication:

        try:

            setter = getattr(

                communication,

                "set_runtime",

                None

            )

            if callable(setter):

                setter(runtime)

            else:

                communication.runtime = runtime

        except Exception:

            pass

    # --------------------------------------------------------
    # AUTONOMY -> LOCALIZATION
    # --------------------------------------------------------

    if autonomy:

        try:

            autonomy.localization = localization

        except Exception:

            pass

        try:

            autonomy.runtime = runtime

        except Exception:

            pass

    # --------------------------------------------------------
    # LOCALIZATION -> DRIVERS
    # --------------------------------------------------------

    if localization:

        try:

            localization.drivers = drivers

        except Exception:

            pass

    print(
        "[BOOT] Subsystem dependency graph connected"
    )

    return True


# ============================================================
# INITIALIZE HOME
# ============================================================

def initialize_home():

    localization = system.get(
        "localization"
    )

    if localization is None:

        print(
            "[BOOT] Localization unavailable; home skipped"
        )

        return False

    # --------------------------------------------------------
    # UPDATE POSITION BEFORE CHECKING HOME
    # --------------------------------------------------------

    try:

        localization.update()

    except Exception:

        pass

    # --------------------------------------------------------
    # RESTORE EXISTING HOME
    # --------------------------------------------------------

    try:

        home = localization.get_home()

    except Exception:

        home = None

    if home:

        print(
            "[BOOT] Persistent home restored"
        )

        print(
            "[BOOT] Home coordinates:",
            home.get("x"),
            home.get("y")
        )

        return True

    # --------------------------------------------------------
    # FIRST BOOT
    # --------------------------------------------------------

    print(
        "[BOOT] No persistent home found"
    )

    print(
        "[BOOT] Capturing startup location as home"
    )

    try:

        localization.set_home()

        print(
            "[BOOT] Home location captured"
        )

        return True

    except Exception as e:

        print(
            "[BOOT] Home capture failed:",
            e
        )

        return False


# ============================================================
# START SERVICES
# ============================================================

def start_services():

    communication = system.get(
        "communication"
    )

    if communication is None:

        return

    try:

        starter = getattr(

            communication,

            "start",

            None

        )

        if callable(starter):

            starter()

            print(
                "[BOOT] Communication service started"
            )

    except Exception as e:

        print(
            "[BOOT] Communication start error:",
            e
        )


# ============================================================
# SYSTEM STATUS
# ============================================================

def print_system_status():

    print("")

    print(
        "================================================"
    )

    print(
        "              SATURDAY STATUS"
    )

    print(
        "================================================"
    )

    for name in system:

        module = system.get(
            name
        )

        state = (

            "ONLINE"

            if module is not None

            else "OFFLINE"

        )

        print(

            "[{}] {}".format(

                state,

                name.upper()

            )

        )

    try:

        print(
            "[MEMORY] Free:",
            gc.mem_free()
        )

    except Exception:

        pass

    print(
        "================================================"
    )

    print("")


# ============================================================
# CLEANUP
# ============================================================

def cleanup():

    for name in list(
        system.keys()
    ):

        module = system.get(
            name
        )

        if module is None:

            continue

        try:

            cleaner = getattr(

                module,

                "cleanup",

                None

            )

            if callable(cleaner):

                cleaner()

        except Exception:

            pass

    try:

        gc.collect()

    except Exception:

        pass


# ============================================================
# BOOT SEQUENCE
# ============================================================

def boot():

    print(
        "[BOOT] Beginning SATURDAY initialization"
    )

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    config = initialize_config()

    # --------------------------------------------------------
    # HARDWARE
    # --------------------------------------------------------

    drivers = initialize_drivers(
        config
    )

    # --------------------------------------------------------
    # EXPRESSION
    # --------------------------------------------------------

    expression = initialize_expression(

        config,

        drivers

    )

    # --------------------------------------------------------
    # COMMUNICATION
    # --------------------------------------------------------

    communication = initialize_communication(

        config,

        drivers

    )

    # --------------------------------------------------------
    # LOCALIZATION
    # --------------------------------------------------------

    localization = initialize_localization(

        config,

        drivers

    )

    # --------------------------------------------------------
    # AUTONOMY
    # --------------------------------------------------------

    autonomy = initialize_autonomy(

        config,

        localization

    )

    # --------------------------------------------------------
    # RUNTIME
    # --------------------------------------------------------

    runtime = initialize_runtime(

        config,

        drivers,

        autonomy,

        communication,

        expression,

        localization

    )

    if runtime is None:

        print(
            "[BOOT] CRITICAL FAILURE"
        )

        return None

    # --------------------------------------------------------
    # CONNECT SYSTEM
    # --------------------------------------------------------

    connect_subsystems()

    # --------------------------------------------------------
    # INITIALIZE HOME
    # --------------------------------------------------------

    initialize_home()

    # --------------------------------------------------------
    # START SERVICES
    # --------------------------------------------------------

    start_services()

    # --------------------------------------------------------
    # MEMORY CLEANUP
    # --------------------------------------------------------

    gc.collect()

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    print_system_status()

    print(
        "[BOOT] SATURDAY READY"
    )

    return runtime


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():

    runtime = boot()

    if runtime is None:

        print(
            "[SYSTEM] Boot failed"
        )

        return

    print("")

    print(
        "================================================"
    )

    print(
        "        SATURDAY IS NOW CONSCIOUS"
    )

    print(
        "================================================"
    )

    print("")

    try:

        runtime.run()

    except KeyboardInterrupt:

        print(
            "[SYSTEM] Shutdown requested"
        )

    except Exception as e:

        print(
            "[SYSTEM] Critical runtime failure:",
            e
        )

        try:

            import sys

            sys.print_exception(e)

        except Exception:

            pass

    finally:

        try:

            runtime.stop()

        except Exception:

            pass

        cleanup()

        print(
            "[SYSTEM] SATURDAY shutdown complete"
        )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    main()