import importlib.util
import unittest

class TrainingAvailable(unittest.TestCase):
    def test_model_preparer_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('microduck_rk.prepare_training'))

if importlib.util.find_spec('microduck_rk.prepare_training'):
    from microduck_rk.prepare_training import validate_inertial
    class InertialTests(unittest.TestCase):
        def test_physical_inertia(self):
            validate_inertial({'mass_kg':.1,'com_m':[0,0,0],'fullinertia_kgm2':[1e-4]*3+[0]*3})
        def test_negative_inertia_refused(self):
            with self.assertRaises(ValueError):
                validate_inertial({'mass_kg':.1,'com_m':[0,0,0],'fullinertia_kgm2':[-1,1,1,0,0,0]})
        def test_triangle_inequality_refused(self):
            with self.assertRaises(ValueError):
                validate_inertial({'mass_kg':.1,'com_m':[0,0,0],'fullinertia_kgm2':[3,1,1,0,0,0]})
        def test_null_measurement_refused(self):
            with self.assertRaises(ValueError):
                validate_inertial({'mass_kg':None,'com_m':[0,0,0],'fullinertia_kgm2':[1,1,1,0,0,0]})
