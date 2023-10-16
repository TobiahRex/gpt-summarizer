import os


def remove_files():
    for file in os.listdir(os.getcwd() + '/lambdas/fxv2/services'):
        os.remove(f'lambdas/fxv2/services/{file}')

    for file in os.listdir(os.getcwd() + '/lambdas/fxv2/constants'):
        os.remove(f'lambdas/fxv2/constants/{file}')

    for file in os.listdir(os.getcwd() + '/lambdas/fxv2/controllers'):
        os.remove(f'lambdas/fxv2/controllers/{file}')


if __name__ == '__main__':
    remove_files()
