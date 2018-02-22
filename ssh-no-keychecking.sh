#!/bin/sh

<<<<<<< HEAD
# Utility script that exec's SSH without key checking so that we can check
# out code from GitHub without prompting the user.
=======
# Verifica via SSH a Key do projeto
>>>>>>> origin/master

exec ssh -o StrictHostKeyChecking=no $@
