from argparse import ArgumentDefaultsHelpFormatter


def func(args, parser):
    from itertools import chain

    import os.path
    import torch
    import torch.optim as optim
    from torch.utils.data import TensorDataset, DataLoader

    from ..models import MolEncoder, MolDecoder
    from ..utils import (load_dataset, train_model, ReduceLROnPlateau,
                         save_checkpoint, validate_model)

    data_train, data_val, charset = load_dataset(args.dataset)

    data_train = torch.from_numpy(data_train)
    data_val = torch.from_numpy(data_val)

    train = TensorDataset(data_train, torch.zeros(data_train.size()[0]))
    train_loader = DataLoader(train, batch_size=args.batch_size, shuffle=True)

    val = TensorDataset(data_val, torch.zeros(data_val.size()[0]))
    val_loader = DataLoader(val, batch_size=args.batch_size, shuffle=True)

    dtype = torch.FloatTensor
    encoder = MolEncoder(c=len(charset))
    decoder = MolDecoder(c=len(charset))

    if args.cuda:
        dtype = torch.cuda.FloatTensor
        encoder.cuda()
        decoder.cuda()

    if args.cont and os.path.isfile('checkpoint.pth.tar'):
        print('Continuing from previous checkpoint...')
        checkpoint = torch.load('checkpoint.pth.tar')
        encoder.load_state_dict(checkpoint['encoder'])
        decoder.load_state_dict(checkpoint['decoder'])
        optimizer = optim.SGD(chain(encoder.parameters(),
                                    decoder.parameters()),
                              lr=args.learning_rate
                              )
        optimizer.load_state_dict(checkpoint['optimizer'])
        best_loss = checkpoint['avg_val_loss']
    else:
        optimizer = optim.SGD(chain(encoder.parameters(),
                                    decoder.parameters()),
                              lr=args.learning_rate
                              )
        best_loss = 1E6

    for param_groups in optimizer.param_groups:
        param_groups['momentum'] = args.momentum
        param_groups['weight_decay'] = args.weight_decay

    scheduler = ReduceLROnPlateau(optimizer, mode='min', min_lr=1E-5)
    for epoch in range(args.num_epochs):
        print('Epoch %s:' % epoch)

        train_model(train_loader, encoder, decoder, optimizer, dtype)
        avg_val_loss = validate_model(val_loader, encoder, decoder, dtype)

        scheduler.step(avg_val_loss, epoch)

        is_best = avg_val_loss < best_loss
        save_checkpoint({
            'epoch': epoch,
            'encoder': encoder.state_dict(),
            'decoder': decoder.state_dict(),
            'avg_val_loss': avg_val_loss,
            'optimizer': optimizer.state_dict(),
        }, is_best)


def configure_parser(sub_parsers):
    help = 'Train autoencoder'
    p = sub_parsers.add_parser('train', description=help, help=help,
                               formatter_class=ArgumentDefaultsHelpFormatter)
    p.add_argument('--dataset', type=str, help="Path to HDF5 dataset",
                   required=True)
    p.add_argument('--num-epochs', type=int, help="Number of epochs",
                   default=1)
    p.add_argument('--batch-size', type=int, help="Batch size", default=250)
    p.add_argument('--learning-rate', type=float, help="Initial learning rate",
                   default=1E-3)
    p.add_argument('--weight-decay', type=float,
                   help="Regularization strength", default=0.)
    p.add_argument('--momentum', type=float, help="Nesterov momentum"",
                   default=0.9)
    p.add_argument('--cuda', help="Use GPU acceleration",
                   action='store_true')
    p.add_argument('--cont', help="Continue from saved state",
                   action='store_true')
    p.set_defaults(func=func)
