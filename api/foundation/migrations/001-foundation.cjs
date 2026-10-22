exports.up = pgm => {
  pgm.sql('REVOKE ALL ON SCHEMA foundation FROM PUBLIC');
  pgm.sql('GRANT USAGE ON SCHEMA foundation TO foundation_runtime');
};

// Forward-only disposable infrastructure; recreate the test environment instead of rolling back.
exports.down = false;
