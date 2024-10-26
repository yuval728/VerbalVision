import torch
import torch.nn as nn

class TimeDistributed(nn.Module):
    def __init__(self, module, batch_first=True):
        super(TimeDistributed, self).__init__()
        self.module = module
        self.batch_first = batch_first

    def forward(self, x):
        if len(x.size()) <= 2:
            return self.module(x)

        # Reshape input: (batch_size, seq_length, ...)
        if self.batch_first:
            x_reshape = x.contiguous().view(-1, *x.size()[2:])  # (batch_size * seq_length, ...)
        else:
            x_reshape = x.contiguous().view(-1, *x.size()[1:])  # (seq_length * batch_size, ...)

        y = self.module(x_reshape)

        # Reshape output back to (batch_size, seq_length, ...)
        if self.batch_first:
            return y.contiguous().view(x.size(0), -1, y.size(-1))  # (batch_size, seq_length, output_size)
        else:
            return y.view(-1, x.size(1), y.size(-1))  # (seq_length, batch_size, output_size)
        
        
class LipNet(nn.Module):
    def __init__(self, vocab_size, input_size, hidden_size=128, num_layers=2, dropout=0.5, input_channels=1):
        super().__init__()
        
        self.vocab_size = vocab_size
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        
        self.conv = nn.Sequential(
            nn.Conv3d(in_channels=input_channels, out_channels=128, kernel_size=3, padding='same'),
            nn.BatchNorm3d(128),
            nn.ReLU(),
            nn.MaxPool3d(kernel_size=(1, 2, 2), stride=(1, 2, 2)),
            
            nn.Conv3d(in_channels=128, out_channels=256, kernel_size=3, padding='same'),
            nn.BatchNorm3d(256),
            nn.ReLU(),
            nn.MaxPool3d(kernel_size=(1, 2, 2), stride=(1, 2, 2)),
            
            nn.Conv3d(in_channels=256, out_channels=75, kernel_size=3, padding='same'),
            # nn.BatchNorm3d(64),
            nn.ReLU(),
            nn.MaxPool3d(kernel_size=(1, 2, 2), stride=(1, 2, 2))
        )
        
        self.flatten = TimeDistributed(nn.Flatten())
        
        self.lstm1 = nn.LSTM(input_size=75 * (46 // 8) * (140 // 8), hidden_size=hidden_size,
                             num_layers=1, batch_first=True, bidirectional=True)
        self.dropout1 = nn.Dropout(self.dropout)
        
        self.lstm2 = nn.LSTM(input_size=256, hidden_size=hidden_size,
                             num_layers=1, batch_first=True, bidirectional=True)
        self.dropout2 = nn.Dropout(self.dropout)
        self.fc = nn.Linear(hidden_size * 2, vocab_size+1)
        
        self.initialize_weights()
        
    def forward(self, x):
        x = self.conv(x)
        x = self.flatten(x)
        
        x, _ = self.lstm1(x)
        x = self.dropout1(x)
        
        x, _ = self.lstm2(x)
        x = self.dropout2(x)
        
        x = self.fc(x)
        
        return x
    
    def initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.LSTM):
                for name, param in m.named_parameters():
                    if 'weight' in name:
                        nn.init.orthogonal_(param)
                    elif 'bias' in name:
                        nn.init.constant_(param, 0)
            elif isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight)
                nn.init.constant_(m.bias, 0)
                
        print('Model weights initialized.')

if __name__ == '__main__':
    import utils
    import constants
    
    word2idx, idx2word = utils.get_word2idx_idx2word(constants.vocab)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    temp_input = torch.randn(4, 75, 1, 46, 140).permute(0, 2, 1, 3, 4).to(device) # (B, C, T, H, W)
    
    model = LipNet(vocab_size=len(word2idx), input_size=75).to(device)
    
    output = model(temp_input)
    print(output.shape)
    
    print('Model architecture:')
    print(model)
    