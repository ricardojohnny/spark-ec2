#!/bin/sh

# Verifica via SSH a Key do projeto
exec ssh -o StrictHostKeyChecking=no $@
